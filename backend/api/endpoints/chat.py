from __future__ import annotations

import asyncio
import base64
import binascii
import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from langchain_core.messages import AIMessage, HumanMessage

from api.schemas.requests import ChatRequest, ChatSessionCreateRequest, DoctorPatientAssignRequest
from api.schemas.responses import AgentResponse, ChatMessageRecord, ChatSessionCreateResponse, ChatSessionSummary
from core.config import settings
from core.exceptions import AgentExecutionError
from graph.graph import run_agent
from services.chat_store import chat_store
from tools.report.patient_pdf import generate_patient_pdf_impl
from tools.utils import decode_image_base64, strip_data_url
from tools.vision.annotator import annotate_xray_image_impl


router = APIRouter(tags=["chat"])


def _to_iso(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def _classify_attachment(attachment: str | None) -> str:
    if not attachment or not attachment.strip():
        return "none"

    normalized = attachment.strip().lower()
    if normalized.startswith("data:"):
        if normalized.startswith("data:image/"):
            return "image"
        try:
            decode_image_base64(attachment)
            return "image"
        except Exception:
            return "document_or_other"

    payload = strip_data_url(attachment)
    try:
        raw = base64.b64decode(payload, validate=False)
    except (ValueError, binascii.Error):
        return "document_or_other"

    if raw.startswith(b"%PDF"):
        return "document_or_other"
    if raw.startswith(b"PK"):
        return "document_or_other"

    try:
        decode_image_base64(attachment)
        return "image"
    except Exception:
        return "document_or_other"


def _extract_latest_image_data(history: list[dict]) -> str | None:
    for item in reversed(history):
        if str(item.get("sender_role") or "") != "user":
            continue
        candidate = item.get("attachment_data_url")
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        if _classify_attachment(candidate) != "image":
            continue
        return candidate
    return None


def _extract_patient_info(history: list[dict], current_message: str, patient_id: str) -> dict[str, Any]:
    merged_text = "\n".join(
        [
            *(str(item.get("content") or "") for item in history[-24:]),
            current_message,
        ]
    )

    info: dict[str, Any] = {"patient_id": patient_id}

    # Accept: "name: John", "name = John", "name - John", "name John", "name chiarg"
    name_match = re.search(
        r"\bname\s*[:=\-]?\s*([A-Za-z][A-Za-z\s\.]{1,60})(?:[,\n]|$)",
        merged_text,
        flags=re.IGNORECASE,
    )
    # Accept: "age: 33", "age = 33", "age 33"
    age_match = re.search(r"\bage\s*[:=\-]?\s*(\d{1,3})\b", merged_text, flags=re.IGNORECASE)
    # Accept: "gender: male", "gender = male", "gemder = male" (typo tolerance via loose prefix)
    gender_match = re.search(
        r"\bge[nm]de?r?\s*[:=\-]?\s*(male|female|other|non-binary|nonbinary)\b",
        merged_text,
        flags=re.IGNORECASE,
    )
    doctor_match = re.search(r"\bdoctor\s*[:=\-]?\s*([A-Za-z][A-Za-z\s\.]{1,60})", merged_text, flags=re.IGNORECASE)

    if name_match:
        info["name"] = name_match.group(1).strip().rstrip(",")
    if age_match:
        try:
            info["age"] = int(age_match.group(1))
        except ValueError:
            pass
    if gender_match:
        info["gender"] = gender_match.group(1).strip().title()
    if doctor_match:
        info["doctor"] = doctor_match.group(1).strip()

    return info


def _missing_patient_fields(patient_info: dict[str, Any]) -> list[str]:
    missing = []
    for key in ("name", "age", "gender"):
        value = patient_info.get(key)
        if isinstance(value, str) and value.strip():
            continue
        if key == "age" and isinstance(value, int):
            continue
        missing.append(key)
    return missing


def _agent_error_message(detail: str) -> str:
    normalized = detail.lower()

    if "rate limit" in normalized or "429" in normalized:
        wait_match = re.search(r"try again in\s+([^\s]+)", detail, flags=re.IGNORECASE)
        wait_hint = wait_match.group(1) if wait_match else None
        if wait_hint:
            return (
                "The AI provider is temporarily rate-limited. "
                f"Please retry after about {wait_hint}, or reduce request size."
            )
        return (
            "The AI provider is temporarily rate-limited. "
            "Please retry shortly, or reduce request size."
        )

    if "openai_api_key" in normalized or "api key" in normalized:
        return (
            "Backend LLM credentials are not configured correctly. "
            "Please verify server environment variables."
        )

    if "400" in normalized or "bad request" in normalized or "invalid" in normalized:
        return (
            "The AI provider rejected the request due to a formatting issue. "
            "Please start a new chat session."
        )

    return (
        "I hit an internal processing issue and could not complete this request. "
        "Please retry in a moment."
    )


def _normalize_role(role: str) -> str:
    value = role.strip().lower()
    if value not in {"doctor", "patient"}:
        raise HTTPException(status_code=400, detail="actor_role must be 'doctor' or 'patient'.")
    return value


def _report_requested(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ("report", "pdf", "document"))


def _history_to_langchain_messages(history: list[dict], current_user_message: str) -> list:
    converted = []
    recent_history = history[-24:]
    for item in recent_history:
        sender = str(item.get("sender_role") or "")
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if sender == "assistant":
            converted.append(AIMessage(content=content))
        else:
            converted.append(HumanMessage(content=content))

    converted.append(HumanMessage(content=current_user_message))
    return converted


async def _build_annotated_image(image_data: str | None, detections: object) -> str | None:
    if not image_data or not isinstance(detections, list):
        return None
    try:
        payload = await annotate_xray_image_impl(image_data, detections)
    except Exception:
        return None
    encoded = payload.get("annotated_image_base64")
    return encoded if isinstance(encoded, str) and encoded else None


async def _ensure_patient_report(
    report_requested: bool,
    diagnosis: object,
    triage: object,
    patient_info: dict[str, Any],
    image_base64: str | None,
    detections: list[dict] | None,
    annotated_image_base64: str | None,
) -> str | None:
    if not report_requested:
        return None
    if not isinstance(diagnosis, dict) or not isinstance(triage, dict):
        return None

    try:
        payload = await generate_patient_pdf_impl(
            diagnosis=diagnosis,
            triage=triage,
            patient_info=patient_info,
            recommendations=[
                str(triage.get("recommended_timeframe") or "Follow clinician guidance promptly."),
                "Bring this report and annotated image for in-person review.",
            ],
            image_base64=image_base64,
            detections=detections,
            annotated_image_base64=annotated_image_base64,
        )
        generated_url = payload.get("pdf_url")
        return generated_url if isinstance(generated_url, str) and generated_url else None
    except Exception:
        return None


async def _ensure_session_access(chat_id: str, actor_id: str, actor_role: str) -> dict:
    session = await chat_store.get_session(chat_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")

    if actor_role == "patient":
        if session.get("patient_id") != actor_id:
            raise HTTPException(status_code=403, detail="Patient is not allowed to access this chat.")
    else:
        if session.get("doctor_id") != actor_id:
            raise HTTPException(status_code=403, detail="Doctor is not allowed to access this chat.")
        patient_id = str(session.get("patient_id") or "")
        if patient_id and patient_id != actor_id and not await chat_store.is_patient_assigned(actor_id, patient_id):
            raise HTTPException(status_code=403, detail="Doctor is not assigned to this patient.")

    return session


@router.post("/chat/assignments")
async def assign_patient(request: DoctorPatientAssignRequest) -> dict:
    await chat_store.assign_patient_to_doctor(request.doctor_id, request.patient_id)
    return {"status": "ok"}


@router.post("/chat/sessions", response_model=ChatSessionCreateResponse)
async def create_chat_session(request: ChatSessionCreateRequest) -> ChatSessionCreateResponse:
    actor_role = _normalize_role(request.actor_role)
    chat_id = str(uuid4())

    if actor_role == "patient":
        patient_id = request.patient_id or request.actor_id
        doctor_id = None
    else:
        if request.patient_id:
            if not await chat_store.is_patient_assigned(request.actor_id, request.patient_id):
                raise HTTPException(status_code=403, detail="Doctor is not assigned to this patient.")
            patient_id = request.patient_id
        else:
            patient_id = request.actor_id
        doctor_id = request.actor_id

    title = (request.title or "New Chat").strip()[:80] or "New Chat"
    await chat_store.create_session(
        chat_id=chat_id,
        actor_id=request.actor_id,
        actor_role=actor_role,
        patient_id=patient_id,
        doctor_id=doctor_id,
        title=title,
    )
    return ChatSessionCreateResponse(chat_id=chat_id, title=title)


@router.get("/chat/sessions", response_model=list[ChatSessionSummary])
async def list_chat_sessions(
    actor_id: str = Query(...),
    actor_role: str = Query(...),
) -> list[ChatSessionSummary]:
    role = _normalize_role(actor_role)
    sessions = await chat_store.list_sessions(actor_id=actor_id, actor_role=role)
    return [
        ChatSessionSummary(
            chat_id=row["chat_id"],
            title=row.get("title") or "New Chat",
            owner_role=row.get("owner_role") or role,
            patient_id=row.get("patient_id") or "",
            doctor_id=row.get("doctor_id"),
            last_message_at=_to_iso(row.get("last_message_at")),
            created_at=_to_iso(row.get("created_at")),
        )
        for row in sessions
    ]


@router.get("/chat/sessions/{chat_id}/messages", response_model=list[ChatMessageRecord])
async def list_chat_messages(
    chat_id: str,
    actor_id: str = Query(...),
    actor_role: str = Query(...),
) -> list[ChatMessageRecord]:
    role = _normalize_role(actor_role)
    await _ensure_session_access(chat_id, actor_id, role)
    messages = await chat_store.get_messages(chat_id)
    return [
        ChatMessageRecord(
            message_id=row.get("message_id") or "",
            chat_id=row.get("chat_id") or chat_id,
            sender_role=row.get("sender_role") or "assistant",
            content=row.get("content") or "",
            attachment_data_url=row.get("attachment_data_url"),
            annotated_image_base64=row.get("annotated_image_base64"),
            agent_trace=row.get("agent_trace") or [],
            created_at=_to_iso(row.get("created_at")),
        )
        for row in messages
    ]


@router.get("/chat/sessions/{chat_id}/trace")
async def get_chat_trace(
    chat_id: str,
    actor_id: str = Query(...),
    actor_role: str = Query(...),
) -> dict:
    role = _normalize_role(actor_role)
    await _ensure_session_access(chat_id, actor_id, role)
    return await chat_store.get_trace(chat_id)


@router.post("/chat/sessions/{chat_id}/messages", response_model=AgentResponse)
async def chat_in_session(chat_id: str, request: ChatRequest) -> AgentResponse:
    actor_role = _normalize_role(request.actor_role)
    session = await _ensure_session_access(chat_id, request.actor_id, actor_role)

    attachment = request.attachment
    message = request.message
    attachment_kind = _classify_attachment(attachment)
    image_data = attachment if attachment_kind == "image" else None
    fresh_image = image_data is not None  # True only when user uploaded image in THIS message
    history_before = await chat_store.get_messages(chat_id)
    if image_data is None:
        image_data = _extract_latest_image_data(history_before)

    if attachment_kind == "document_or_other":
        message = (
            f"{request.message}\n\n"
            "[Attachment note: a non-image file was uploaded. "
            "Current vision analysis supports image uploads only. "
            "Proceed with text guidance and ask for an X-ray image for visual analysis.]"
        )

    user_message_id = str(uuid4())
    await chat_store.append_message(
        chat_id=chat_id,
        message_id=user_message_id,
        sender_role="user",
        content=request.message,
        attachment_data_url=attachment,
    )

    patient_info = _extract_patient_info(
        history=history_before,
        current_message=message,
        patient_id=str(session.get("patient_id") or request.patient_id or request.actor_id),
    )
    # For doctor role, inject actor_name as the referring doctor (only if it looks like a real name)
    clean_actor_name = (request.actor_name or "").strip()
    # Reject Clerk user-IDs (e.g. "user_2vXyz...") — they are not display names
    if clean_actor_name.startswith("user_") or not any(c.isalpha() for c in clean_actor_name):
        clean_actor_name = ""
    if actor_role == "doctor" and clean_actor_name:
        patient_info.setdefault("doctor", clean_actor_name)

    # ── Load persisted clinical pipeline state from previous turns ────────────
    pipeline_state = await chat_store.get_pipeline_state(chat_id)
    stored_patient_info: dict = pipeline_state.pop("patient_info", {}) or {}
    # Merge persisted patient_info with freshly-extracted one (fresh extraction wins for present fields)
    merged_patient_info = {**stored_patient_info, **{k: v for k, v in patient_info.items() if v}}

    payload = {
        "session_id": chat_id,
        "user_message": message,
        "messages": _history_to_langchain_messages(history_before, message),
        "image_data": image_data,
        "patient_id": session.get("patient_id") or request.patient_id,
        "location": request.location,
        "actor_role": actor_role,
        "actor_name": clean_actor_name or "",
        "patient_info": merged_patient_info,
        # Re-inject clinical pipeline state from previous turns so the agent has context
        **pipeline_state,
    }

    try:
        result = await asyncio.wait_for(
            run_agent(payload),
            timeout=max(5, settings.chat_request_timeout_seconds),
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Chat request timed out.")
    except AgentExecutionError as exc:
        raise HTTPException(status_code=500, detail=_agent_error_message(str(exc))) from exc

    detections = result.get("detections")
    # Only annotate when the user actually uploaded a fresh image this turn
    annotated_image_base64 = await _build_annotated_image(image_data, detections) if fresh_image else None
    final_response = result.get("final_response") or "No response generated."
    assistant_message_id = str(uuid4())
    trace = result.get("agent_trace") or []

    # ── Persist updated clinical pipeline state back to session ──────────────
    new_pipeline: dict = {}
    for _k in ("diagnosis", "triage_result", "body_part", "detections"):
        _v = result.get(_k)
        if _v is not None:
            new_pipeline[_k] = _v
    # Track pending_report flag (None means clear it)
    _pending = result.get("pending_report_actor_role")
    new_pipeline["pending_report_actor_role"] = _pending  # explicit None clears it in MongoDB via $set
    # Merge patient_info: stored + newly extracted, always keep the most complete version
    result_pi = result.get("patient_info") or {}
    best_pi = {**stored_patient_info, **{k: v for k, v in merged_patient_info.items() if v}, **{k: v for k, v in result_pi.items() if v}}
    if best_pi:
        new_pipeline["patient_info"] = best_pi
    if new_pipeline:
        try:
            await chat_store.save_pipeline_state(chat_id, new_pipeline)
        except Exception:
            pass

    # Report URL comes exclusively from the agent graph.
    report_url = result.get("report_url") if isinstance(result.get("report_url"), str) else None

    if report_url and report_url not in final_response:
        final_response = f"{final_response}\n\nReport: {report_url}"

    await chat_store.append_message(
        chat_id=chat_id,
        message_id=assistant_message_id,
        sender_role="assistant",
        content=final_response,
        annotated_image_base64=annotated_image_base64,
        agent_trace=trace,
    )

    return AgentResponse(
        chat_id=chat_id,
        message_id=assistant_message_id,
        session_id=chat_id,
        final_response=final_response,
        body_part=result.get("body_part"),
        diagnosis=result.get("diagnosis"),
        triage=result.get("triage_result"),
        hospitals=result.get("hospitals"),
        report_url=report_url,
        annotated_image_base64=annotated_image_base64,
        agent_trace=trace,
    )


@router.post("/chat", response_model=AgentResponse)
async def chat_with_agent(request: ChatRequest) -> AgentResponse:
    actor_role = _normalize_role(request.actor_role)
    chat_id = request.session_id

    if not chat_id:
        if actor_role == "patient":
            patient_id = request.patient_id or request.actor_id
            doctor_id = None
        else:
            if request.patient_id:
                if not await chat_store.is_patient_assigned(request.actor_id, request.patient_id):
                    raise HTTPException(status_code=403, detail="Doctor is not assigned to this patient.")
                patient_id = request.patient_id
            else:
                patient_id = request.actor_id
            doctor_id = request.actor_id

        title_source = request.message.strip() or "New Chat"
        chat_id = str(uuid4())
        await chat_store.create_session(
            chat_id=chat_id,
            actor_id=request.actor_id,
            actor_role=actor_role,
            patient_id=patient_id,
            doctor_id=doctor_id,
            title=title_source[:80],
        )

    bridged = ChatRequest(
        actor_id=request.actor_id,
        actor_role=actor_role,
        actor_name=request.actor_name,
        message=request.message,
        session_id=chat_id,
        attachment=request.attachment,
        patient_id=request.patient_id,
        location=request.location,
    )
    return await chat_in_session(chat_id, bridged)


@router.get("/patients")
async def list_patients(
    actor_id: str = Query(...),
    actor_role: str = Query(...),
) -> list[dict[str, Any]]:
    """Derive a patient list from chat sessions + pipeline state."""
    role = _normalize_role(actor_role)
    sessions = await chat_store.list_sessions(actor_id=actor_id, actor_role=role)

    seen: dict[str, dict[str, Any]] = {}
    for session in sessions:
        pid = session.get("patient_id") or ""
        if not pid or pid == actor_id:
            continue

        pipeline_info: dict[str, Any] = {}
        for key in ("pipeline_patient_info", "pipeline_triage_result", "pipeline_body_part", "pipeline_diagnosis"):
            val = session.get(key)
            if val:
                pipeline_info[key] = val

        patient_info = pipeline_info.get("pipeline_patient_info") or {}
        triage = pipeline_info.get("pipeline_triage_result") or {}
        diagnosis = pipeline_info.get("pipeline_diagnosis") or {}

        triage_level = str(triage.get("triage_level") or triage.get("urgency_level") or "").upper()
        risk = "GREEN"
        if triage_level in ("RED", "HIGH", "URGENT", "EMERGENCY"):
            risk = "RED"
        elif triage_level in ("AMBER", "MEDIUM", "MODERATE"):
            risk = "AMBER"

        name = str(patient_info.get("name") or patient_info.get("patient_name") or pid)
        age = patient_info.get("age")
        summary_text = str(diagnosis.get("summary") or diagnosis.get("description") or triage.get("recommendation") or "")

        last_msg = session.get("last_message_at")
        last_study = _to_iso(last_msg) if last_msg else ""

        if pid not in seen:
            seen[pid] = {
                "id": pid,
                "name": name,
                "age": int(age) if age is not None and str(age).isdigit() else 0,
                "riskLevel": risk,
                "summary": summary_text or "No summary available yet.",
                "lastStudy": last_study[:10] if last_study else "",
            }
        else:
            existing = seen[pid]
            if name != pid and existing["name"] == pid:
                existing["name"] = name
            if age and not existing["age"]:
                existing["age"] = int(age) if str(age).isdigit() else 0
            if risk == "RED" or (risk == "AMBER" and existing["riskLevel"] == "GREEN"):
                existing["riskLevel"] = risk
            if summary_text and existing["summary"] == "No summary available yet.":
                existing["summary"] = summary_text
            if last_study and last_study > existing["lastStudy"]:
                existing["lastStudy"] = last_study[:10]

    return list(seen.values())
