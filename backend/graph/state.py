from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # Input
    session_id: str
    user_message: str
    image_data: str | None
    symptoms: str | None
    patient_id: str | None
    location: str | None
    actor_role: str | None        # "doctor" or "patient"
    actor_name: str | None        # display name from Clerk

    # Discovered during execution
    body_part: str | None
    detections: list[dict] | None
    diagnosis: dict[str, Any] | None
    triage_result: dict[str, Any] | None
    knowledge_context: dict[str, Any] | None
    hospitals: list[dict] | None
    report_url: str | None
    patient_info: dict[str, Any] | None   # name, age, gender, doctor, body_part collected from conversation
    pending_report_actor_role: str | None  # set when a report was requested but gated on missing patient info
    multi_agent_insights: dict[str, Any] | None
    multi_agent_coordination: dict[str, Any] | None
    multi_agent_enabled: bool | None
    tool_execution_outcomes: list[dict[str, Any]] | None

    # LangGraph internals
    messages: Annotated[list[BaseMessage], add_messages]
    tool_calls_made: list[str]
    agent_trace: list[dict[str, Any]]
    current_agent: str | None
    iteration_count: int
    error: str | None
    final_response: str | None


def base_state() -> AgentState:
    return {
        "image_data": None,
        "symptoms": None,
        "patient_id": None,
        "location": None,
        "body_part": None,
        "detections": None,
        "diagnosis": None,
        "triage_result": None,
        "hospitals": None,
        "report_url": None,
        "patient_info": None,
        "pending_report_actor_role": None,
        "multi_agent_insights": None,
        "multi_agent_coordination": None,
        "multi_agent_enabled": False,
        "tool_execution_outcomes": None,
        "messages": [],
        "tool_calls_made": [],
        "agent_trace": [],
        "current_agent": None,
        "iteration_count": 0,
        "error": None,
        "final_response": None,
    }
