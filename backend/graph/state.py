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

    # Multi-modal input
    modality: str | None          # "xray" | "ct" | "mri"
    body_region: str | None       # "hand" | "leg" | "knee" | "spine" | "foot" | "pelvis" | "shoulder"
    volume_path: str | None       # Path to NIfTI volume on disk (for CT/MRI tools)
    dicom_metadata: dict[str, Any] | None  # Extracted DICOM tags

    # Discovered during execution
    body_part: str | None
    detections: list[dict] | None       # X-ray findings (from YOLO)
    ct_findings: list[dict] | None      # CT findings (from TotalSegmentator/VerSe)
    mri_findings: list[dict] | None     # MRI findings (from kneeseg/TotalSegmentator)
    diagnosis: dict[str, Any] | None
    triage_result: dict[str, Any] | None
    knowledge_context: dict[str, Any] | None
    hospitals: list[dict] | None
    report_url: str | None
    annotated_slices_base64: list[str] | None  # Annotated key slices for CT/MRI
    patient_info: dict[str, Any] | None   # name, age, gender, doctor, body_part collected from conversation
    pending_report_actor_role: str | None  # set when a report was requested but gated on missing patient info
    multi_agent_insights: dict[str, Any] | None
    multi_agent_coordination: dict[str, Any] | None
    multi_agent_enabled: bool | None
    tool_execution_outcomes: list[dict[str, Any]] | None

    # Care-plan agent outputs (populated by care_plan_node after diagnosis+triage are ready)
    treatment_plan: dict[str, Any] | None
    rehabilitation_plan: dict[str, Any] | None
    patient_education: dict[str, Any] | None
    appointment_schedule: dict[str, Any] | None
    care_plan_generated: bool | None

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
        "modality": None,
        "body_region": None,
        "volume_path": None,
        "dicom_metadata": None,
        "body_part": None,
        "detections": None,
        "ct_findings": None,
        "mri_findings": None,
        "diagnosis": None,
        "triage_result": None,
        "hospitals": None,
        "report_url": None,
        "annotated_slices_base64": None,
        "patient_info": None,
        "pending_report_actor_role": None,
        "multi_agent_insights": None,
        "multi_agent_coordination": None,
        "multi_agent_enabled": False,
        "tool_execution_outcomes": None,
        "treatment_plan": None,
        "rehabilitation_plan": None,
        "patient_education": None,
        "appointment_schedule": None,
        "care_plan_generated": False,
        "messages": [],
        "tool_calls_made": [],
        "agent_trace": [],
        "current_agent": None,
        "iteration_count": 0,
        "error": None,
        "final_response": None,
    }
