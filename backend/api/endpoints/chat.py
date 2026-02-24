from __future__ import annotations

import asyncio
import base64
import binascii
import re
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from api.schemas.requests import ChatRequest, ChatSessionCreateRequest, DoctorPatientAssignRequest
from api.schemas.responses import AgentResponse, ChatMessageRecord, ChatSessionCreateResponse, ChatSessionSummary
from core.config import settings
from core.exceptions import AgentExecutionError
from graph.graph import run_agent
from services.chat_store import chat_store
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


async def _build_annotated_image(image_data: str | None, detections: object) -> str | None:
    if not image_data or not isinstance(detections, list):
        return None
    try:
        payload = await annotate_xray_image_impl(image_data, detections)
    except Exception:
        return None
    encoded = payload.get("annotated_image_base64")
    return encoded if isinstance(encoded, str) and encoded else None


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
        report_url=result.get("report_url"),
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
