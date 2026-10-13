import json

from fastapi import APIRouter, HTTPException, Request, status
from langchain_core.messages import HumanMessage

from app.core.dependency import currentUser
from app.core.logger import logger
from app.schemas.chat import ChatMessageRequest
from app.services.agent_brain import compiled_agent_brain_graph

router = APIRouter()

@router.post("/send-message", status_code=status.HTTP_200_OK)
async def chat_conversation(request: Request, payload: ChatMessageRequest, current_user: currentUser) -> dict:
    try:

        logger.info("user Id: %s", current_user)

        initial_graph_state_input = {
            "messages": [HumanMessage(content=payload.prompt)],
            "user_id": current_user,
            "auth_cookies": dict(request.cookies),
        }

        graph_configurable_metadata_context = {
            "configurable": {
                "thread_id": payload.thread_id
            }
        }

        logger.info("Ingestion Portal: Handing off runtime conversation state variables array straight to LangGraph Brain Engine...")
        logger.info("Before graph invocation")
        logger.info("Initial state types: %s", {
            key: type(value).__name__
            for key, value in initial_graph_state_input.items()
        })

        final_graph_output_state_delta = await compiled_agent_brain_graph.ainvoke(
            initial_graph_state_input,
            config=graph_configurable_metadata_context
        )
        logger.info("After graph invocation")
        updated_messages_history_pool = final_graph_output_state_delta.get("messages", [])
        final_ai_reply_message_object = updated_messages_history_pool[-1] if updated_messages_history_pool else None
        final_bot_response_text_string = final_ai_reply_message_object.content if final_ai_reply_message_object else "No response generated."

        logger.info("Final message count: %d", len(updated_messages_history_pool))
        logger.info("Final message type: %s", type(final_ai_reply_message_object).__name__)
        logger.info("Final response type: %s", type(final_bot_response_text_string).__name__)

        response_payload = {
            "response": final_bot_response_text_string,
            "user_id": current_user,
            "thread_id": payload.thread_id,
            "status": "success"
        }
        logger.info("Validating response JSON serialization")
        json.dumps(response_payload)
        logger.info("Response JSON serialization successful")
        return response_payload

    except Exception as route_err:
        logger.exception("AI chat endpoint failed:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(route_err)}"
        ) from route_err