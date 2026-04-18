from __future__ import annotations

import json
from functools import lru_cache

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode
from loguru import logger

from graph.state import AgentState
from services.chat_store import chat_store
from services.probabilistic_reasoning import bayesian_updater
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


def _inject_volume_data_into_medical_calls(state: AgentState) -> AgentState:
    volume_path = state.get("volume_path")
    if not isinstance(volume_path, str) or not volume_path.strip():
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
        if not (name.startswith("ct_") or name.startswith("mri_")):
            updated_calls.append(call)
            continue

        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        if args.get("volume_path") != volume_path:
            call = {**call, "args": {**args, "volume_path": volume_path}}
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


def _planned_tool_trace_events(state: AgentState) -> tuple[list[dict], list[str]]:
    messages = list(state.get("messages", []))
    if not messages:
        return [], []

    last_message = messages[-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    if not isinstance(tool_calls, list):
        return [], []

    events: list[dict] = []
    long_running_tools: list[str] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        tool_name = str(call.get("name", "")).strip()
        if not tool_name:
            continue
        events.append(
            {
                "type": "tool_execution_started",
                "tool_name": tool_name,
            }
        )
        if tool_name.startswith(("ct_", "mri_")):
            long_running_tools.append(tool_name)

    return events, long_running_tools


async def _tool_progress_heartbeat(session_id: str, tool_names: list[str]) -> None:
    while True:
        await asyncio.sleep(15)
        for tool_name in tool_names:
            try:
                await chat_store.append_trace_event(
                    session_id,
                    {
                        "type": "tool_progress",
                        "tool_name": tool_name,
                        "message": "Still running. Volumetric analysis is in progress.",
                    },
                )
            except Exception:
                continue


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
    ct_findings = state.get("ct_findings") if isinstance(state.get("ct_findings"), list) else []
    mri_findings = state.get("mri_findings") if isinstance(state.get("mri_findings"), list) else []
    unified_findings = detections or ct_findings or mri_findings
    patient_id = str(state.get("patient_id") or "unknown")
    body_part = str(state.get("body_part") or state.get("body_region") or "unknown")
    report_url = state.get("report_url")
    actor_name = str(state.get("actor_name") or "")
    actor_role = str(state.get("actor_role") or "patient").lower()

    # Build enriched patient_info from state (name/age/gender extracted from conversation)
    _state_pi = state.get("patient_info") or {}
    _enriched_pi: dict = {
        "patient_id": str(_state_pi.get("patient_id") or patient_id),
        "body_part": body_part,
    }
    for _k in ("name", "age", "gender", "doctor"):
        _v = _state_pi.get(_k)
        if _v:
            _enriched_pi[_k] = _v
    # For doctor role, the referring doctor IS the logged-in doctor
    if actor_role == "doctor" and actor_name:
        _enriched_pi["doctor"] = actor_name

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
                merged["detections"] = unified_findings
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
                merged["detections"] = unified_findings
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
            if not isinstance(merged.get("patient_info"), dict) or not merged["patient_info"].get("name"):
                merged["patient_info"] = _enriched_pi
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
                _sid = str(state.get("session_id") or "")
                _study_id = f"OA-{_sid[:8].upper()}" if _sid else "OA-UNKNOWN"
                merged["metadata"] = {
                    "patient_id": patient_id,
                    "body_part": body_part,
                    "study_id": _study_id,
                    "doctor_name": actor_name,
                    "actor_name": actor_name,
                }
            call = {**call, "args": merged}
            changed = True

        if name == "report_generate_clinician_simple_pdf":
            merged = {**args}
            if not isinstance(merged.get("diagnosis"), dict):
                merged["diagnosis"] = diagnosis
            if not isinstance(merged.get("triage"), dict):
                merged["triage"] = triage
            if not isinstance(merged.get("detections"), list):
                merged["detections"] = detections
            if not isinstance(merged.get("metadata"), dict):
                merged["metadata"] = {
                    "patient_id": _enriched_pi.get("patient_id", patient_id),
                    "body_part": body_part,
                    "study_id": f"OA-{str(state.get('session_id') or '')[:8].upper()}" or "OA-UNKNOWN",
                    "doctor_name": actor_name if actor_role == "doctor" else _enriched_pi.get("doctor", ""),
                    "actor_name": actor_name,
                    "patient_name": _enriched_pi.get("name", ""),
                    "patient_age": str(_enriched_pi.get("age", "")),
                    "patient_gender": _enriched_pi.get("gender", ""),
                }
            else:
                # Enrich existing metadata
                meta = merged["metadata"]
                if not meta.get("body_part"):
                    meta["body_part"] = body_part
                if not meta.get("doctor_name") and actor_role == "doctor":
                    meta["doctor_name"] = actor_name
            if not isinstance(merged.get("recommendations"), list) or not merged.get("recommendations"):
                merged["recommendations"] = _default_recommendations(state)
            if not isinstance(merged.get("image_base64"), str) or not str(merged.get("image_base64")).strip():
                merged["image_base64"] = state.get("image_data")
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
    prepared_state = _inject_volume_data_into_medical_calls(prepared_state)
    prepared_state = _inject_state_into_report_calls(prepared_state)
    session_id = state.get("session_id", "unknown")
    planned_trace_events, long_running_tools = _planned_tool_trace_events(prepared_state)
    for event in planned_trace_events:
        try:
            await chat_store.append_trace_event(session_id, event)
        except Exception:
            pass

    heartbeat_task: asyncio.Task | None = None
    if long_running_tools:
        heartbeat_task = asyncio.create_task(_tool_progress_heartbeat(session_id, long_running_tools))

    try:
        result = await get_tool_executor_node().ainvoke(prepared_state, config=config)
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    updates: dict = {}
    trace_events: list[dict] = []

    # Track tool execution outcomes for learning
    tool_execution_outcomes = []

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

        # Determine tool execution success for learning
        execution_success = True
        execution_error = None

        try:
            # Check for common error indicators in tool results
            if isinstance(payload, dict):
                if payload.get("error"):
                    execution_success = False
                    execution_error = payload.get("error")
                elif payload.get("success") == False:
                    execution_success = False
                    execution_error = payload.get("message", "Tool execution failed")
                # For vision tools, check if detections are valid
                elif message.name.startswith("vision_"):
                    detections = payload.get("detections", [])
                    if not detections or (isinstance(detections, list) and len(detections) == 0):
                        # Vision tool failed to detect anything
                        execution_success = False
                        execution_error = "No detections found"
                elif message.name.startswith("ct_") or message.name.startswith("mri_"):
                    findings = payload.get("findings", [])
                    if not findings or (isinstance(findings, list) and len(findings) == 0):
                        execution_success = False
                        execution_error = "No findings returned"
                # For clinical tools, check if results are valid
                elif message.name.startswith("clinical_"):
                    if not payload or (
                        isinstance(payload, dict)
                        and not payload.get("diagnosis")
                        and not payload.get("triage_result")
                        and not payload.get("finding")
                        and not payload.get("level")
                    ):
                        execution_success = False
                        execution_error = "No valid clinical results"

            # Record execution outcome for learning
            tool_execution_outcomes.append({
                "tool_name": message.name,
                "success": execution_success,
                "error": execution_error,
                "payload": payload
            })

            # Update Bayesian beliefs based on execution outcome
            try:
                bayesian_updater.update_belief(message.name, execution_success)
                logger.info(
                    "session={} Updated Bayesian belief for {}: success={}, error={}",
                    session_id, message.name, execution_success, execution_error
                )
            except Exception as e:
                logger.warning(
                    "session={} Failed to update Bayesian belief for {}: {}",
                    session_id, message.name, e
                )

        except Exception as e:
            logger.error(
                "session={} Error processing tool execution for {}: {}",
                session_id, message.name, e
            )
            tool_execution_outcomes.append({
                "tool_name": message.name,
                "success": False,
                "error": str(e),
                "payload": payload
            })

        if message.name == "modality_detect_imaging_modality":
            updates["modality"] = payload.get("modality")
            if payload.get("body_part_suggestion"):
                updates["body_region"] = payload.get("body_part_suggestion")
        elif message.name == "modality_parse_dicom":
            updates["dicom_metadata"] = payload.get("metadata")
            if payload.get("body_part"):
                updates["body_region"] = payload.get("body_part")
            if payload.get("modality"):
                updates["modality"] = payload.get("modality")
        elif message.name == "modality_extract_mid_slice":
            if payload.get("mid_slice_base64"):
                updates["annotated_slices_base64"] = [payload.get("mid_slice_base64")]
        elif message.name == "vision_detect_body_part":
            updates["body_part"] = payload.get("body_part")
        elif message.name in {"vision_detect_hand_fracture", "vision_detect_leg_fracture"}:
            updates["detections"] = payload.get("detections", [])
        elif message.name.startswith("ct_"):
            updates["ct_findings"] = payload.get("findings", [])
            if payload.get("annotated_slices_base64"):
                updates["annotated_slices_base64"] = payload.get("annotated_slices_base64")
        elif message.name.startswith("mri_"):
            updates["mri_findings"] = payload.get("findings", [])
            if payload.get("annotated_slices_base64"):
                updates["annotated_slices_base64"] = payload.get("annotated_slices_base64")
        elif message.name == "clinical_generate_diagnosis":
            updates["diagnosis"] = payload
        elif message.name == "clinical_assess_triage":
            updates["triage_result"] = payload
        elif message.name == "hospital_find_nearby_hospitals":
            updates["hospitals"] = payload.get("hospitals", [])
        elif message.name in {"report_generate_patient_pdf", "report_generate_clinician_pdf", "report_generate_clinician_simple_pdf"}:
            updates["report_url"] = payload.get("pdf_url")

    if planned_trace_events or trace_events:
        updates["agent_trace"] = [*state.get("agent_trace", []), *planned_trace_events, *trace_events]

    # Store tool execution outcomes for learning system
    if tool_execution_outcomes:
        updates["tool_execution_outcomes"] = tool_execution_outcomes

        try:
            await chat_store.append_trace_event(
                session_id,
                {
                    "type": "tool_execution_summary",
                    "tool_outcomes": tool_execution_outcomes,
                    "total_tools_executed": len(tool_execution_outcomes),
                    "successful_executions": sum(1 for o in tool_execution_outcomes if o["success"]),
                    "failed_executions": sum(1 for o in tool_execution_outcomes if not o["success"])
                }
            )
        except Exception:
            logger.warning(
                "session={} Failed to store tool execution outcomes for learning",
                session_id
            )

    return {**result, **updates}
