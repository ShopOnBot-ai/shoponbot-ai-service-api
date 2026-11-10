import time
from pprint import pformat
from typing import Annotated, TypedDict

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
)
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import StreamWriter
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings
from app.core.llm import llm_chat_engine
from app.core.logger import logger
from app.services.tools import fetch_user_cart_data, search_products_tool

db_url = settings.database_url.replace("+asyncpg", "")

MAX_HISTORY_MESSAGES = 12

pool = AsyncConnectionPool(
    conninfo=db_url,
    max_size=10,
    kwargs={"autocommit": True},
    open=False,
)

checkpointer = AsyncPostgresSaver(pool)

SYSTEM_PROMPT = """You are ShopOnBot, a shopping assistant for an Indian online store.
- All prices are in Indian rupees. Always write prices as ₹ (for example ₹657), never $.
- Use the search_products tool to find products and the fetch_user_cart_data tool for cart questions.
- Answer ONLY from tool results. Never invent products, prices, colours or availability.
- If a tool returns no products, say that no matching products were found.
- List each product with its name and price. Keep answers short and do not add generic disclaimers."""

ANSWER_PROMPT = """You are ShopOnBot, a shopping assistant for an Indian online store.
Write the final reply to the customer using ONLY the tool result in the conversation above.
- Prices are in Indian rupees; write them as ₹ (for example ₹657), never $.
- Never invent products, prices or colours.
- If the tool result says no products were found, say that clearly.
- Reply in plain sentences. Never output JSON or tool calls."""

TOOLS_BY_NAME = {
    "fetch_user_cart_data": fetch_user_cart_data,
    "search_products": search_products_tool,
}

def chunk_text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") for p in content if isinstance(p, dict))

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: int


async def call_llm_model_node(state: AgentState, writer: StreamWriter) -> dict:
    logger.info("============== ENTERING LLM NODE ==============")
    messages = state.get("messages", [])

    # use for sent only last 12 history messages to the LLM instead of sending all history this will reduce token cost
    recent = trim_messages(
        messages,
        strategy="last",
        token_counter=len,
        max_tokens=MAX_HISTORY_MESSAGES,
        start_on="human",
        include_system=False,
    )

    last_message = messages[-1] if messages else None
    if isinstance(last_message, ToolMessage):
        model = llm_chat_engine
        prompt = [SystemMessage(content=ANSWER_PROMPT), *recent]
    else:
        model = llm_chat_engine.bind_tools([fetch_user_cart_data, search_products_tool])
        prompt = [SystemMessage(content=SYSTEM_PROMPT), *recent]

    full: AIMessageChunk | None = None
    async for chunk in model.astream(prompt):
        full = chunk if full is None else full + chunk
        if chunk.tool_call_chunks or chunk.tool_calls:
            continue
        text = chunk_text(chunk.content)
        if text:
            writer({"token": text})
    
    return {"messages": [full]}


async def determine_next_routing_path_edge(state: AgentState) -> str:
    logger.info("=============== ROUTING DECISION ENGINE ===============")

    message_list = state.get("messages", [])

    if not message_list:
        logger.warning("Warning: Empty message stream. Terminating graph routing execution loop.")
        return "terminate_chat"

    last_message = message_list[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        detected_tool = [call["name"] for call in last_message.tool_calls]
        logger.info("LLM Intent Unlocked: Activating tool mapping for -> [ %s ]", detected_tool)
        return "continue_tools"

    logger.info("LLM Text Stream Finalised: Redirecting workflow stream straight to END target.")
    logger.info("==========================================================================")
    return "terminate_chat"


async def execute_tool_node(state: AgentState, config: RunnableConfig) -> dict:
    logger.info("================= EXECUTING TOOL NODE =================")

    last_message = state.get("messages", [])[-1]
    tool_messages = []

    for tool_call in last_message.tool_calls:
        name = tool_call["name"]
        tool_args = dict(tool_call["args"])
        tool = TOOLS_BY_NAME.get(name)

        if tool is None:
            result = f"Error: unknown tool '{name}'."
        else:
            start = time.perf_counter()
            try:
                result = await tool.ainvoke(tool_args, config=config)
            except Exception as err:
                logger.exception("Tool %s failed: %s", name, err)
                result = f"Error: the tool '{name}' failed. Please try again."
            logger.info("Tool %s took %.3fs", name, time.perf_counter() - start)

        logger.info("Tool output for %s: %s", name, result)
        tool_messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))

    return {"messages": tool_messages}


workflow_graph_builder = StateGraph(AgentState)
workflow_graph_builder.add_node("oracle_llm", call_llm_model_node)
workflow_graph_builder.add_node("action_tools", execute_tool_node)
workflow_graph_builder.set_entry_point("oracle_llm")
workflow_graph_builder.add_conditional_edges(
    "oracle_llm",
    determine_next_routing_path_edge,
    {"continue_tools": "action_tools", "terminate_chat": END},
)
workflow_graph_builder.add_edge("action_tools", "oracle_llm")
compiled_agent_brain_graph = workflow_graph_builder.compile(checkpointer=checkpointer)