from __future__ import annotations

from functools import lru_cache
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from loguru import logger

from core.config import settings
from core.exceptions import AgentExecutionError
from graph.checkpointer import get_checkpointer
from graph.nodes.error_handler import error_handler_node
from graph.nodes.response_builder import response_builder_node
from graph.nodes.supervisor import supervisor_node
from graph.nodes.tool_executor import tool_executor_node
from graph.state import AgentState, base_state
from services.chat_store import chat_store


def _report_requested(state: AgentState) -> bool:
    text = str(state.get("user_message") or "").lower().strip()
    report_keywords = ("report", "pdf", "document")
    type_keywords = ("summary", "quick", "simple", "simplified", "full", "clinical",
                     "detailed", "depth", "complete", "comprehensive")
    if any(keyword in text for keyword in report_keywords):
        return True
    # Treat type-selection responses as report requests when pipeline is complete
    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")
    if diagnosis and triage and not state.get("report_url"):
        if any(keyword in text for keyword in type_keywords):
            return True
        # Also handle numbered choices "1" / "2" as report type selection
        if text in ("1", "2"):
            return True
    return False


def should_continue(state: AgentState) -> str:
    if state.get("iteration_count", 0) >= settings.max_agent_iterations:
        return "error_handler"
    if state.get("error"):
        return "error_handler"

    messages = state.get("messages", [])
    if not messages:
        return "response_builder"

    last_message = messages[-1]

    # If supervisor returned tool calls, always execute them first
    if getattr(last_message, "tool_calls", None):
        return "tool_executor"

    # No tool calls — decide whether to end or loop back
    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")
    report_url = state.get("report_url")
    tool_calls_made = state.get("tool_calls_made", [])
    report_tool_attempts = sum(
        1 for name in tool_calls_made if name in {
            "report_generate_patient_pdf",
            "report_generate_clinician_pdf",
            "report_generate_clinician_simple_pdf",
        }
    )

    # If pipeline complete and either: report done, report not requested, or already attempted
    if diagnosis and triage:
        if not _report_requested(state):
            return "response_builder"
        if report_url:
            return "response_builder"
        if report_tool_attempts >= 1:
            return "response_builder"

    return "response_builder"


def error_handler_route(state: AgentState) -> str:
    if state.get("final_response"):
        return "response_builder"
    if state.get("iteration_count", 0) >= settings.max_agent_iterations:
        return "response_builder"
    return "supervisor"


@lru_cache(maxsize=1)
def get_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("tool_executor", tool_executor_node)
    workflow.add_node("response_builder", response_builder_node)
    workflow.add_node("error_handler", error_handler_node)

    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        should_continue,
        {
            "tool_executor": "tool_executor",
            "response_builder": "response_builder",
            "error_handler": "error_handler",
        },
    )
    workflow.add_edge("tool_executor", "supervisor")
    workflow.add_conditional_edges(
        "error_handler",
        error_handler_route,
        {"supervisor": "supervisor", "response_builder": "response_builder"},
    )
    workflow.add_edge("response_builder", END)

    return workflow.compile(checkpointer=get_checkpointer())


async def run_agent(payload: dict) -> AgentState:
    graph = get_graph()
    state = base_state()
    state.update(payload)

    session_id = state.get("session_id") or str(uuid4())
    user_message = state.get("user_message") or "Analyze the case with available context."

    state["session_id"] = session_id
    if not state.get("messages"):
        state["messages"] = [HumanMessage(content=user_message)]

    try:
        await chat_store.init_trace(session_id)
    except Exception:
        pass
    logger.info("session={} agent_run_started", session_id)

    try:
        result = await graph.ainvoke(state, config={"configurable": {"thread_id": f"{session_id}:{uuid4()}"}})
    except Exception as exc:
        logger.exception("session={} agent_run_failed", session_id)
        raise AgentExecutionError(str(exc)) from exc

    logger.info(
        "session={} agent_run_completed iterations={} active_agent={}",
        session_id,
        result.get("iteration_count", 0),
        result.get("current_agent") or "none",
    )

    try:
        await chat_store.complete_trace(session_id, result.get("agent_trace", []))
    except Exception:
        pass

    return result
