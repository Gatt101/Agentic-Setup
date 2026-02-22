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

    # Discovered during execution
    body_part: str | None
    detections: list[dict] | None
    diagnosis: dict[str, Any] | None
    triage_result: dict[str, Any] | None
    hospitals: list[dict] | None
    report_url: str | None

    # LangGraph internals
    messages: Annotated[list[BaseMessage], add_messages]
    tool_calls_made: list[str]
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
        "messages": [],
        "tool_calls_made": [],
        "current_agent": None,
        "iteration_count": 0,
        "error": None,
        "final_response": None,
    }
