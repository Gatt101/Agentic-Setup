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

    name_match = re.search(r"\bname\s*[:=-]\s*([A-Za-z][A-Za-z\s]{1,60})", merged_text, flags=re.IGNORECASE)
    age_match = re.search(r"\bage\s*[:=-]\s*(\d{1,3})\b", merged_text, flags=re.IGNORECASE)
    gender_match = re.search(
        r"\b(gender|sex)\s*[:=-]\s*(male|female|other|non-binary|nonbinary)\b",
        merged_text,
        flags=re.IGNORECASE,
    )
    doctor_match = re.search(r"\bdoctor\s*[:=-]\s*([A-Za-z][A-Za-z\s\.]{1,60})", merged_text, flags=re.IGNORECASE)

    if name_match:
        info["name"] = name_match.group(1).strip()
    if age_match:
        try:
            info["age"] = int(age_match.group(1))
        except ValueError:
            pass
    if gender_match:
        info["gender"] = gender_match.group(2).strip().title()
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

    payload = {
        "session_id": chat_id,
        "user_message": message,
        "messages": _history_to_langchain_messages(history_before, message),
        "image_data": image_data,
        "patient_id": session.get("patient_id") or request.patient_id,
        "location": request.location,
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
    annotated_image_base64 = await _build_annotated_image(image_data, detections)
    final_response = result.get("final_response") or "No response generated."
    assistant_message_id = str(uuid4())
    trace = result.get("agent_trace") or []
    patient_info = _extract_patient_info(
        history=history_before,
        current_message=request.message,
        patient_id=str(session.get("patient_id") or request.actor_id),
    )
    report_url = await _ensure_patient_report(
        report_requested=_report_requested(request.message),
        diagnosis=result.get("diagnosis"),
        triage=result.get("triage_result"),
        patient_info=patient_info,
        image_base64=image_data,
        detections=detections if isinstance(detections, list) else None,
        annotated_image_base64=annotated_image_base64,
    )
    if not report_url:
        report_url = result.get("report_url") if isinstance(result.get("report_url"), str) else None

    if report_url and _report_requested(request.message) and report_url not in final_response:
        final_response = f"{final_response}\n\nPatient report: {report_url}"

    if _report_requested(request.message):
        missing = _missing_patient_fields(patient_info)
        if missing:
            final_response += (
                "\n\nFor a fuller report profile, please share: "
                + ", ".join(missing)
                + "."
            )

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
        message=request.message,
        session_id=chat_id,
        attachment=request.attachment,
        patient_id=request.patient_id,
        location=request.location,
    )
    return await chat_in_session(chat_id, bridged)
