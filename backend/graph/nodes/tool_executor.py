from __future__ import annotations

import json
from functools import lru_cache

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode
from loguru import logger

from graph.state import AgentState
from services.chat_store import chat_store
from tools import ALL_TOOLS


@lru_cache(maxsize=1)
def get_tool_executor_node() -> ToolNode:
    # ToolNode is the canonical agentic executor for supervisor-selected tool calls.
    return ToolNode(ALL_TOOLS, handle_tool_errors=True)


def _coerce_tool_payload(message: ToolMessage) -> dict:
    content = message.content
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def _inject_image_data_into_vision_calls(state: AgentState) -> AgentState:
    image_data = state.get("image_data")
    if not isinstance(image_data, str) or not image_data.strip():
        return state

    messages = list(state.get("messages", []))
    if not messages:
        return state

    last_message = messages[-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    if not isinstance(tool_calls, list):
        return state

    changed = False
    updated_calls = []

    for call in tool_calls:
        if not isinstance(call, dict):
            updated_calls.append(call)
            continue

        name = str(call.get("name", ""))
        if not name.startswith("vision_"):
            updated_calls.append(call)
            continue

        args = call.get("args")
        if not isinstance(args, dict):
            args = {}

        if args.get("image_base64") != image_data:
            args = {**args, "image_base64": image_data}
            call = {**call, "args": args}
            changed = True

        updated_calls.append(call)

    if not changed:
        return state

    try:
        messages[-1] = last_message.model_copy(update={"tool_calls": updated_calls})
    except Exception:
        return state

    return {**state, "messages": messages}


def _default_recommendations(state: AgentState) -> list[str]:
    triage = state.get("triage_result")
    diagnosis = state.get("diagnosis")
    recommendations: list[str] = []

    if isinstance(triage, dict):
        timeframe = str(triage.get("recommended_timeframe") or "").strip()
        if timeframe:
            recommendations.append(timeframe)

    if isinstance(diagnosis, dict):
        finding = str(diagnosis.get("finding") or "").strip()
        if finding:
            recommendations.append(f"Follow-up for finding: {finding}.")

    recommendations.append("Seek clinician confirmation for final treatment plan.")
    return recommendations


def _inject_state_into_report_calls(state: AgentState) -> AgentState:
    messages = list(state.get("messages", []))
    if not messages:
        return state

    last_message = messages[-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    if not isinstance(tool_calls, list):
        return state

    diagnosis = state.get("diagnosis") if isinstance(state.get("diagnosis"), dict) else {}
    triage = state.get("triage_result") if isinstance(state.get("triage_result"), dict) else {}
    detections = state.get("detections") if isinstance(state.get("detections"), list) else []
    patient_id = str(state.get("patient_id") or "unknown")
    body_part = str(state.get("body_part") or "unknown")
    report_url = state.get("report_url")

    changed = False
    updated_calls = []
    for call in tool_calls:
        if not isinstance(call, dict):
            updated_calls.append(call)
            continue

        name = str(call.get("name", ""))
        args = call.get("args")
        if not isinstance(args, dict):
            args = {}

        if name == "clinical_generate_diagnosis":
            merged = {**args}
            if not isinstance(merged.get("detections"), list):
                merged["detections"] = detections
            if not isinstance(merged.get("symptoms"), str) or not str(merged.get("symptoms")).strip():
                merged["symptoms"] = str(state.get("symptoms") or "")
            if not isinstance(merged.get("body_part"), str) or not str(merged.get("body_part")).strip():
                merged["body_part"] = body_part
            call = {**call, "args": merged}
            changed = True

        if name == "clinical_assess_triage":
            merged = {**args}
            if not isinstance(merged.get("diagnosis"), dict):
                merged["diagnosis"] = diagnosis
            if not isinstance(merged.get("detections"), list):
                merged["detections"] = detections
            if not isinstance(merged.get("patient_vitals"), str) or not str(merged.get("patient_vitals")).strip():
                merged["patient_vitals"] = str(state.get("symptoms") or "")
            call = {**call, "args": merged}
            changed = True

        if name == "report_generate_patient_pdf":
            merged = {**args}
            if not isinstance(merged.get("diagnosis"), dict):
                merged["diagnosis"] = diagnosis
            if not isinstance(merged.get("triage"), dict):
                merged["triage"] = triage
            if not isinstance(merged.get("patient_info"), dict):
                merged["patient_info"] = {"patient_id": patient_id}
            if not isinstance(merged.get("recommendations"), list) or not merged.get("recommendations"):
                merged["recommendations"] = _default_recommendations(state)
            if not isinstance(merged.get("image_base64"), str) or not str(merged.get("image_base64")).strip():
                merged["image_base64"] = state.get("image_data")
            if not isinstance(merged.get("detections"), list):
                merged["detections"] = detections
            call = {**call, "args": merged}
            changed = True

        if name == "report_generate_clinician_pdf":
            merged = {**args}
            if not isinstance(merged.get("detections"), list):
                merged["detections"] = detections
            if not isinstance(merged.get("triage"), dict):
                merged["triage"] = triage
            if not isinstance(merged.get("images"), dict):
                merged["images"] = {"annotated_image_url": report_url or ""}
            if not isinstance(merged.get("metadata"), dict):
                merged["metadata"] = {
                    "patient_id": patient_id,
                    "body_part": body_part,
                }
            call = {**call, "args": merged}
            changed = True

        updated_calls.append(call)

    if not changed:
        return state

    try:
        messages[-1] = last_message.model_copy(update={"tool_calls": updated_calls})
    except Exception:
        return state

    return {**state, "messages": messages}


async def tool_executor_node(state: AgentState, config=None) -> dict:
    # Important: forward runtime config from graph execution to avoid missing runtime keys.
    prepared_state = _inject_image_data_into_vision_calls(state)
    prepared_state = _inject_state_into_report_calls(prepared_state)
    result = await get_tool_executor_node().ainvoke(prepared_state, config=config)
    updates: dict = {}
    session_id = state.get("session_id", "unknown")
    trace_events: list[dict] = []

    for message in result.get("messages", []):
        if not isinstance(message, ToolMessage):
            continue

        logger.info("session={} tool_executed={}", session_id, message.name)
        trace_events.append(
            {
                "type": "tool_execution",
                "tool_name": message.name,
            }
        )
        try:
            await chat_store.append_trace_event(
                session_id,
                {
                    "type": "tool_execution",
                    "tool_name": message.name,
                },
            )
        except Exception:
            pass

        payload = _coerce_tool_payload(message)
        if not payload:
            continue

        if message.name == "vision_detect_body_part":
            updates["body_part"] = payload.get("body_part")
        elif message.name in {"vision_detect_hand_fracture", "vision_detect_leg_fracture"}:
            updates["detections"] = payload.get("detections", [])
        elif message.name == "clinical_generate_diagnosis":
            updates["diagnosis"] = payload
        elif message.name == "clinical_assess_triage":
            updates["triage_result"] = payload
        elif message.name == "hospital_find_nearby_hospitals":
            updates["hospitals"] = payload.get("hospitals", [])
        elif message.name in {"report_generate_patient_pdf", "report_generate_clinician_pdf"}:
            updates["report_url"] = payload.get("pdf_url")

    if trace_events:
        updates["agent_trace"] = [*state.get("agent_trace", []), *trace_events]

    return {**result, **updates}
