import json
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langfuse import get_client, propagate_attributes
from langfuse.langchain import CallbackHandler

from app.core.dependency import currentUser
from app.core.logger import logger
from app.schemas.chat import ChatMessageRequest
from app.services.agent_brain import chunk_text, compiled_agent_brain_graph

router = APIRouter()

langfuse_client = get_client()

def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

def get_thread_id(user_id) -> str:
    return f"user_thread_{user_id}"


async def stream_agent_events(
    request: Request, graph_input: dict, config: dict, thread_id: str, user_id:str
) -> AsyncIterator[str]:
    t0 = time.perf_counter()
    ttft: float | None = None
    sent = 0

    try:
        with propagate_attributes(user_id=str(user_id), session_id=thread_id):
            async for part in compiled_agent_brain_graph.astream(
                graph_input, config=config, stream_mode="custom"
            ):
                logger.info("part: %s", part)
                if await request.is_disconnected():
                    return
                text = part.get("token") if isinstance(part, dict) else None
                if not text:
                    continue
                if ttft is None:
                    ttft = time.perf_counter() - t0
                sent += 1
                yield sse("token", {"text": text})

            if sent == 0:
                logger.warning("stream fallback used: no tokens came from the custom stream")
                state = await compiled_agent_brain_graph.aget_state(config)
                msgs = state.values.get("messages", [])
                text = chunk_text(msgs[-1].content) if msgs else ""
                if text:
                    ttft = ttft or (time.perf_counter() - t0)
                    yield sse("token", {"text": text})

            total = time.perf_counter() - t0
            logger.info("stream done: ttft=%.2fs total=%.2fs chunks=%d", ttft or -1, total, sent)
            yield sse("done", {
                "thread_id": thread_id,
                "ttft_ms": round(ttft * 1000) if ttft else None,
                "total_ms": round(total * 1000),
            })
    except Exception:
        logger.exception("AI stream failed")
        yield sse("error", {"message": "Something went wrong. Please try again."})
    finally:
        get_client().flush()

@router.post("/send-message", status_code=status.HTTP_200_OK, response_model=None)
async def chat_conversation(request: Request, payload: ChatMessageRequest, current_user: currentUser):

    auth_cookies = {k: v for k, v in request.cookies.items() if k == "access_token"}

    initial_graph_state_input = {
        "messages": [HumanMessage(content=payload.prompt)],
        "user_id": current_user,
    }

    langfuse_handler = CallbackHandler()

    with propagate_attributes(
        user_id=str(current_user),
        session_id=get_thread_id(current_user)
    ):

        config = {
            "configurable": {
                "thread_id": get_thread_id(current_user),
                "auth_cookies": auth_cookies
            },
            "callbacks": [langfuse_handler]
        }

        if payload.stream:
            return StreamingResponse(
                stream_agent_events(request, initial_graph_state_input, config, get_thread_id(current_user), current_user),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        logger.info("Ingestion Portal: Handing off runtime conversation state variables array straight to LangGraph Brain Engine...")

        try:
            final_state = await compiled_agent_brain_graph.ainvoke(
                initial_graph_state_input,
                config=config
            )
            messages = final_state.get("messages", [])
            reply = messages[-1].content if messages else "No response generated."

            return {
                "response": reply,
                "user_id": current_user,
                "thread_id": get_thread_id(current_user),
                "status": "success"
            }

        except Exception as route_err:
            logger.exception("AI chat endpoint failed:")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal server error: {str(route_err)}"
            ) from route_err


@router.get("/history")
async def get_history(current_user: currentUser):
    config = {"configurable": {"thread_id": get_thread_id(current_user)}}
    state = await compiled_agent_brain_graph.aget_state(config)
    msgs = state.values.get("messages", []) if state and state.values else []
    return [
        {"role": "user" if m.type == "human" else "assistant", "content": m.content}
        for m in msgs
        if m.type in ("human", "ai") and m.content and not getattr(m, "tool_calls", None)
    ]