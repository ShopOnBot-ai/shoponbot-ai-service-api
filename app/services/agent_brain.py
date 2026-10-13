from pprint import pformat
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.core.llm import llm_chat_engine
from app.core.logger import logger
from app.services.tools import fetch_user_cart_data


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: int
    auth_cookies: dict[str, str]


async def call_llm_model_node(state: AgentState) -> dict:
    logger.info("============== ENTERING LLM NODE ==============")
    conversation_messages_list = state.get("messages", [])
    logger.info("Current Central State Message History Count: %d",len(conversation_messages_list),)
    logger.debug("Complete History Snapshot:\n%s", pformat(conversation_messages_list))

    llm_with_tools = llm_chat_engine.bind_tools([fetch_user_cart_data])
    logger.info("Framework Engine: Forwarding full context array pipeline to Ollama window...")

    llm_response = await llm_with_tools.ainvoke(conversation_messages_list)
    
    logger.info("Core LLM response token snapshot received back successfully.")
    logger.info("Raw LLM Response Object State:\n%s", pformat(llm_response))
    
    logger.info("Node processing finished. Dispatching state payload delta updates.")
    return {"messages": [llm_response]}


async def determine_next_routing_path_edge(state: AgentState) -> str:
    logger.info("=============== ROUTING DECISION ENGINE ===============")

    message_list = state.get("messages", [])

    if not message_list:
        logger.warning("Warning: Empty message stream. Terminating graph routing execution loop.")
        return "terminate_chat"

    last_message = message_list[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        detected_tool = last_message.tool_calls[0]["name"]
        logger.info("LLM Intent Unlocked: Activating tool mapping for -> [ %s ]", detected_tool)
        return "continue_tools"

    logger.info("LLM Text Stream Finalised: Redirecting workflow stream straight to END target.")
    logger.info("==========================================================================")
    return "terminate_chat"


async def execute_tool_node(state: AgentState) -> dict:
    logger.info("================= EXECUTING TOOL NODE =================")

    message_list = state.get("messages", [])
    last_message = message_list[-1]

    tool_call = last_message.tool_calls[0]

    tool_args = dict(tool_call["args"])

    tool_args["cookies"] = state["auth_cookies"]

    tool_result_string = await fetch_user_cart_data.ainvoke(tool_args)

    logger.info("Tool output successfully generated: %s", tool_result_string)

    return {
        "messages": [ToolMessage(content=tool_result_string, tool_call_id=tool_call["id"])]
    }


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
memory_saver_checkpoint = MemorySaver()
compiled_agent_brain_graph = workflow_graph_builder.compile(checkpointer=memory_saver_checkpoint)