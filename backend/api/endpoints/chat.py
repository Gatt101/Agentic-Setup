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
from loguru import logger

from api.schemas.requests import ChatRequest, ChatSessionCreateRequest, DoctorPatientAssignRequest
from api.schemas.responses import AgentResponse, ChatMessageRecord, ChatSessionCreateResponse, ChatSessionSummary
from core.config import settings
from core.exceptions import AgentExecutionError
from services.chat_store import chat_store
from services.mongo import mongo_service
from services.patient_store import patient_store
from tools.modality.dicom_utils import (
    dicom_bytes_to_image_data_url,
    dicom_bytes_to_nifti_file,
    dicom_series_to_nifti_file,
    extract_dicom_files_from_zip_bytes,
    is_dicom,
    normalize_body_part,
    normalize_dicom_series,
    read_dicom_metadata,
)
from tools.report.clinician_simple_pdf import generate_clinician_simple_pdf_impl
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
        if "application/dicom" in normalized:
            return "dicom"
        if normalized.startswith("data:image/"):
            return "image"
        try:
            raw = base64.b64decode(strip_data_url(attachment), validate=False)
            if is_dicom(raw):
                return "dicom"
            if raw.startswith(b"PK"):
                try:
                    if extract_dicom_files_from_zip_bytes(raw):
                        return "dicom"
                except Exception:
                    pass
            decode_image_base64(attachment)
            return "image"
        except Exception:
            return "document_or_other"

    payload = strip_data_url(attachment)
    try:
        raw = base64.b64decode(payload, validate=False)
    except (ValueError, binascii.Error):
        return "document_or_other"

    if is_dicom(raw):
        return "dicom"

    if raw.startswith(b"%PDF"):
        return "document_or_other"
    if raw.startswith(b"PK"):
        try:
            if extract_dicom_files_from_zip_bytes(raw):
                return "dicom"
        except Exception:
            pass
        return "document_or_other"

    try:
        decode_image_base64(attachment)
        return "image"
    except Exception:
        return "document_or_other"


def _decode_base64_payload(payload: str) -> bytes:
    body = payload.split(",", 1)[1] if payload.strip().startswith("data:") and "," in payload else payload
    return base64.b64decode(body)


def _normalize_attachments(request: ChatRequest) -> list[str]:
    attachments = [item for item in (request.attachments or []) if isinstance(item, str) and item.strip()]
    if attachments:
        return attachments
    if isinstance(request.attachment, str) and request.attachment.strip():
        return [request.attachment]
    return []


def _validate_volumetric_series(
    *,
    modality: str | None,
    metadata: dict[str, Any],
    volume_info: dict[str, Any],
) -> str | None:
    if modality not in {"ct", "mri"}:
        return None

    spacing = volume_info.get("spacing")
    slice_thickness = metadata.get("slice_thickness_mm")
    slice_count = int(volume_info.get("slice_count") or 0)

    spacing_z = None
    if isinstance(spacing, list) and len(spacing) >= 3:
        try:
            spacing_z = float(spacing[2])
        except Exception:
            spacing_z = None

    try:
        nominal_thickness = float(slice_thickness) if slice_thickness is not None else None
    except Exception:
        nominal_thickness = None

    if spacing_z is not None and nominal_thickness is not None:
        if spacing_z > max(5.0, nominal_thickness * 3.0):
            return (
                "The uploaded CT/MRI series appears incomplete or has missing slices. "
                f"Detected z-spacing is {spacing_z:.2f} mm while slice thickness is {nominal_thickness:.2f} mm. "
                "Please upload the full contiguous DICOM series or a zip exported from the viewer/PACS."
            )

    if slice_count and slice_count < 8 and spacing_z is not None and spacing_z >= 3.0:
        return (
            "The uploaded CT/MRI series is too sparse for reliable 3D analysis. "
            f"Only {slice_count} slices were assembled with {spacing_z:.2f} mm z-spacing. "
            "Please upload the full DICOM series instead of a partial selection."
        )

    return None


def _prepare_attachment_inputs(session_id: str, attachments: list[str]) -> dict[str, Any]:
    attachment = attachments[0] if attachments else None
    attachment_kind = _classify_attachment(attachment)
    prepared: dict[str, Any] = {
        "attachment_kind": attachment_kind,
        "image_data": attachment if attachment_kind == "image" else None,
        "volume_path": None,
        "dicom_metadata": None,
        "modality": None,
        "body_region": None,
        "error_message": None,
    }

    if not attachments:
        return prepared

    attachment_kinds = [_classify_attachment(item) for item in attachments]
    if any(kind != "dicom" for kind in attachment_kinds):
        return prepared

    prepared["attachment_kind"] = "dicom"

    dicom_entries = []
    for item in attachments:
        raw_payload = _decode_base64_payload(item)
        payloads = [raw_payload]
        if not is_dicom(raw_payload):
            payloads = extract_dicom_files_from_zip_bytes(raw_payload)
        for dicom_bytes in payloads:
            metadata = read_dicom_metadata(dicom_bytes)
            dicom_entries.append({
                "attachment": item,
                "bytes": dicom_bytes,
                "metadata": metadata,
            })

    if not dicom_entries:
        prepared["error_message"] = "The uploaded archive does not contain any readable DICOM files."
        return prepared

    normalized_entries, normalization_info = normalize_dicom_series(
        [entry["bytes"] for entry in dicom_entries]
    )
    dicom_entries = normalized_entries

    first_entry = dicom_entries[0]
    metadata = first_entry["metadata"]
    modality = metadata.get("modality")
    body_region = normalize_body_part(
        str(metadata.get("body_part_examined") or ""),
        str(metadata.get("study_description") or ""),
        str(metadata.get("series_description") or ""),
    )

    prepared["dicom_metadata"] = metadata
    prepared["modality"] = modality
    prepared["body_region"] = body_region

    if modality == "xray":
        prepared["image_data"] = dicom_bytes_to_image_data_url(first_entry["bytes"])
        return prepared

    if modality in {"ct", "mri"} and len(dicom_entries) < 2:
        prepared["error_message"] = (
            "This CT/MRI upload contains only a single DICOM slice. Volumetric analysis requires the full DICOM series, "
            "so please upload multiple slices from the same study together."
        )
        return prepared

    settings.dicom_storage_path.mkdir(parents=True, exist_ok=True)
    settings.nifti_storage_path.mkdir(parents=True, exist_ok=True)
    nifti_path = settings.nifti_storage_path / f"{session_id}.nii.gz"
    if len(dicom_entries) == 1:
        dicom_path = settings.dicom_storage_path / f"{session_id}.dcm"
        dicom_path.write_bytes(first_entry["bytes"])
        volume_path, volume_info = dicom_bytes_to_nifti_file(first_entry["bytes"], str(nifti_path))
    else:
        volume_path, volume_info = dicom_series_to_nifti_file(
            [entry["bytes"] for entry in dicom_entries],
            str(nifti_path),
        )
    volumetric_error = _validate_volumetric_series(
        modality=modality,
        metadata=metadata,
        volume_info=volume_info,
    )
    if volumetric_error:
        prepared["error_message"] = volumetric_error
        return prepared
    prepared["volume_path"] = volume_path
    prepared["dicom_metadata"] = {
        **metadata,
        **normalization_info,
        **volume_info,
        "slice_count": len(dicom_entries),
    }
    return prepared


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
    # Only search USER messages — AI messages contain field labels like
    # "Full name / Age / Gender" which poison the regex (e.g. name→"Age").
    user_history_text = "\n".join(
        str(item.get("content") or "")
        for item in history[-24:]
        if str(item.get("sender_role") or "") == "user"
    )
    merged_text = user_history_text + "\n" + current_message

    info: dict[str, Any] = {"patient_id": patient_id}

    # Accept:
    # "name: John", "full name: John", "name = John", "name - John",
    # "my name is John", "patient name is John"
    name_match = re.search(
        r"\b(?:(?:my|patient)\s+)?(?:full\s*name|name)\s*(?:(?:[:=\-])|\bis\b)?\s*"
        r"([A-Za-z][A-Za-z\s\.\'-]{1,60}?)"
        r"(?=\s*(?:,|\n|age\b|aged\b|ge[nm]de?r?\b|doctor\b|give\b|gen\b|pdf\b|$))",
        merged_text,
        flags=re.IGNORECASE,
    )
    # Accept: "age: 33", "age = 33", "age 33", "age is 33"
    age_match = re.search(
        r"\b(?:age|aged)\s*(?:(?:[:=\-])|\bis\b)?\s*(\d{1,3})\b",
        merged_text,
        flags=re.IGNORECASE,
    )
    # Accept: "gender: male", "gender = male", "gender: m", "gender is male", "gemder = male"
    gender_match = re.search(
        r"\bge[nm]de?r?\s*(?:(?:[:=\-])|\bis\b)?\s*(male|female|other|non-binary|nonbinary|m|f)\b",
        merged_text,
        flags=re.IGNORECASE,
    )
    doctor_match = re.search(
        r"\bdoctor\s*(?:(?:[:=\-])|\bis\b)?\s*([A-Za-z][A-Za-z\s\.]{1,60})",
        merged_text,
        flags=re.IGNORECASE,
    )

    if name_match:
        info["name"] = name_match.group(1).strip().rstrip(",")
    if age_match:
        try:
            info["age"] = int(age_match.group(1))
        except ValueError:
            pass
    if gender_match:
        raw_gender = gender_match.group(1).strip().lower()
        if raw_gender == "m":
            info["gender"] = "Male"
        elif raw_gender == "f":
            info["gender"] = "Female"
        else:
            info["gender"] = raw_gender.title()
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


def _same_patient_value(left: Any, right: Any) -> bool:
    if left is None and right is None:
        return True
    if isinstance(left, int) or isinstance(right, int):
        try:
            return int(left) == int(right)
        except Exception:
            return False
    return str(left or "").strip().lower() == str(right or "").strip().lower()


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


def _chat_timeout_seconds(*, volume_path: str | None, modality: str | None) -> int:
    base_timeout = max(5, settings.chat_request_timeout_seconds)
    if volume_path or modality in {"ct", "mri"}:
        return max(base_timeout, settings.volumetric_chat_timeout_seconds)
    return base_timeout


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


async def _ensure_report(
    report_requested: bool,
    actor_role: str,
    diagnosis: object,
    triage: object,
    patient_info: dict[str, Any],
    image_base64: str | None,
    detections: list[dict] | None,
    annotated_image_base64: str | None,
) -> tuple[str | None, str | None]:
    if not report_requested:
        return None, None
    if not isinstance(diagnosis, dict) or not isinstance(triage, dict):
        return None, "Clinical analysis is incomplete, so a report cannot be generated yet."

    missing_fields = _missing_patient_fields(patient_info)
    if actor_role != "doctor" and missing_fields:
        return None, (
            "Before I regenerate the PDF, I still need the patient's "
            + ", ".join(missing_fields)
            + "."
        )

    try:
        if actor_role == "doctor":
            payload = await generate_clinician_simple_pdf_impl(
                diagnosis=diagnosis,
                triage=triage,
                metadata={
                    "patient_id": str(patient_info.get("patient_id") or "unknown"),
                    "body_part": str(patient_info.get("body_part") or ""),
                    "doctor_name": str(patient_info.get("doctor") or ""),
                    "patient_name": str(patient_info.get("name") or ""),
                    "patient_age": str(patient_info.get("age") or ""),
                    "patient_gender": str(patient_info.get("gender") or ""),
                },
                recommendations=[
                    str(triage.get("recommended_timeframe") or "Follow clinical protocol for this triage level."),
                    "Review the annotated image alongside the patient history.",
                ],
                image_base64=image_base64,
                detections=detections,
                annotated_image_base64=annotated_image_base64,
            )
        else:
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
        if isinstance(generated_url, str) and generated_url:
            return generated_url, None
        return None, "The report tool returned no PDF URL."
    except Exception as exc:
        logger.exception("Direct report generation fallback failed")
        return None, f"Report generation failed: {exc}"


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

    # ── Inject intake greeting so the first thing the user sees is a request
    #    for patient details — used for report generation and analysis.
    clean_name = (request.actor_name or "").strip()
    if clean_name.startswith("user_") or not any(c.isalpha() for c in clean_name):
        clean_name = ""

    if actor_role == "doctor":
        salutation = f"Hello, Dr. {clean_name}!" if clean_name else "Hello, Doctor!"
        greeting = (
            f"👋 {salutation} I'm **OrthoAssist**, your AI-powered orthopedic assistant.\n\n"
            "To get started, please provide your **patient's details** so I can personalise "
            "the analysis and include them in any reports:\n\n"
            "- **Full Name**\n"
            "- **Age**\n"
            "- **Gender** (Male / Female / Other)\n\n"
            "You can type them in one message, e.g.:\n"
            "> *Name: John Smith, Age: 45, Gender: Male*\n\n"
            "Once you share those, upload an X-ray or describe the case and I'll begin the analysis!"
        )
    else:
        salutation = f"Hello, {clean_name}!" if clean_name else "Hello!"
        greeting = (
            f"👋 {salutation} I'm **OrthoAssist**, your AI-powered orthopedic assistant.\n\n"
            "Before we begin, please share a few details so I can personalise your analysis "
            "and any reports generated for you:\n\n"
            "- **Your Full Name**\n"
            "- **Age**\n"
            "- **Gender** (Male / Female / Other)\n\n"
            "You can type them in one message, e.g.:\n"
            "> *Name: Sarah Jones, Age: 34, Gender: Female*\n\n"
            "After that, upload your X-ray image and I'll analyse it for you!"
        )

    greet_id = str(uuid4())
    try:
        await chat_store.append_message(
            chat_id=chat_id,
            message_id=greet_id,
            sender_role="assistant",
            content=greeting,
        )
    except Exception:
        pass  # greeting failure must never block session creation

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
    from graph.graph import run_agent

    actor_role = _normalize_role(request.actor_role)
    session = await _ensure_session_access(chat_id, request.actor_id, actor_role)

    attachments = _normalize_attachments(request)
    attachment = attachments[0] if attachments else None
    message = request.message
    attachment_inputs = _prepare_attachment_inputs(chat_id, attachments)
    attachment_kind = attachment_inputs["attachment_kind"]
    image_data = attachment_inputs["image_data"]
    volume_path = attachment_inputs["volume_path"]
    dicom_metadata = attachment_inputs["dicom_metadata"]
    modality = attachment_inputs["modality"]
    body_region = attachment_inputs["body_region"]
    attachment_error_message = attachment_inputs["error_message"]
    fresh_image = image_data is not None  # True only when user uploaded image in THIS message
    fresh_visual_input = bool(image_data or volume_path)
    history_before = await chat_store.get_messages(chat_id)
    if image_data is None and volume_path is None:
        image_data = _extract_latest_image_data(history_before)

    # When the user sends a fresh image, they are starting a new analysis —
    # clear any pending report flag so we don't immediately ask for patient info.
    _clear_pending_on_fresh = fresh_visual_input

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

    if attachment_error_message:
        assistant_message_id = str(uuid4())
        await chat_store.append_message(
            chat_id=chat_id,
            message_id=assistant_message_id,
            sender_role="assistant",
            content=attachment_error_message,
        )
        return AgentResponse(
            chat_id=chat_id,
            message_id=assistant_message_id,
            session_id=chat_id,
            final_response=attachment_error_message,
            agent_trace=[],
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
    # mongo_patient_id is our internal tracking key — exclude from agent payload
    _existing_mongo_patient_id: str | None = pipeline_state.pop("mongo_patient_id", None)

    # Detect whether this message is an analysis request (not a report request)
    _msg_lower = message.lower().strip()
    _ANALYSIS_KEYWORDS = ("analys", "detect", "fracture", "scan", "xray", "x-ray",
                          "check", "examine", "look at", "diagnos", "assess")
    _REPORT_KEYWORDS = ("report", "pdf", "document")
    _is_analysis_request = (
        any(k in _msg_lower for k in _ANALYSIS_KEYWORDS)
        and not any(k in _msg_lower for k in _REPORT_KEYWORDS)
    )

    # Clear pending report flag when:
    #   a) user sent a fresh image (new analysis session), OR
    #   b) user message is an analysis request (not a report request)
    if _clear_pending_on_fresh or _is_analysis_request:
        logger.info("chat_id={} clearing pending_report + clinical state (fresh_image={} analysis_keyword={})",
                    chat_id, fresh_visual_input, _is_analysis_request)
        pipeline_state["pending_report_actor_role"] = None
        # Wipe stale clinical data so the pipeline restarts cleanly
        for _stale_key in ("diagnosis", "triage_result", "body_part", "detections", "report_url", "image_data", "volume_path", "dicom_metadata", "modality", "body_region"):
            pipeline_state.pop(_stale_key, None)

    # Merge persisted patient_info with freshly-extracted one (fresh extraction wins for present fields)
    merged_patient_info = {**stored_patient_info, **{k: v for k, v in patient_info.items() if v}}
    if _existing_mongo_patient_id:
        merged_patient_info["patient_id"] = _existing_mongo_patient_id

    _report_requested_now = any(k in _msg_lower for k in _REPORT_KEYWORDS)
    _provided_patient_updates = {
        key: patient_info.get(key)
        for key in ("name", "age", "gender", "doctor")
        if patient_info.get(key) not in (None, "")
    }
    _patient_info_changed_for_report = any(
        not _same_patient_value(value, stored_patient_info.get(key))
        for key, value in _provided_patient_updates.items()
    )

    if _report_requested_now and _patient_info_changed_for_report:
        logger.info(
            "chat_id={} report request includes updated patient info; clearing stale report_url",
            chat_id,
        )
        pipeline_state.pop("report_url", None)

    logger.info("chat_id={} actor_role={} fresh_image={} patient_info_keys={}",
                chat_id, actor_role, fresh_visual_input, list(merged_patient_info.keys()))

    # ── Fast-path: pure intake message (name/age/gender, no image, no analysis/report keyword) ──
    # Skip the agent entirely so the LLM never gets a chance to re-ask for info
    # or incorrectly fire the report gate.
    _pi_name = str(merged_patient_info.get("name") or "").strip()
    _pi_age = merged_patient_info.get("age")
    _pi_gender = str(merged_patient_info.get("gender") or "").strip()
    _intake_complete = bool(_pi_name) and (_pi_age is not None) and bool(_pi_gender)
    _intake_fields_mentioned = ("name" in _msg_lower or "age" in _msg_lower or "gender" in _msg_lower)
    if _intake_complete and mongo_service.enabled and (_existing_mongo_patient_id is None or _intake_fields_mentioned):
        try:
            _upserted_pre = await patient_store.upsert_patient(
                name=_pi_name,
                age=int(_pi_age) if _pi_age is not None else None,
                gender=_pi_gender,
                doctor_user_id=request.actor_id if actor_role == "doctor" else None,
                patient_user_id=request.actor_id if actor_role == "patient" else None,
                chat_id=chat_id,
                existing_patient_id=_existing_mongo_patient_id,
            )
            _existing_mongo_patient_id = str(_upserted_pre["patient_id"])
            merged_patient_info["patient_id"] = _existing_mongo_patient_id
            logger.info("chat_id={} intake patient upserted patient_id={}", chat_id, _existing_mongo_patient_id)
        except Exception as _pre_upsert_err:
            logger.warning("chat_id={} pre-agent patient upsert failed: {}", chat_id, _pre_upsert_err)

    _is_intake_only = (
        not fresh_image
        and not any(k in _msg_lower for k in _ANALYSIS_KEYWORDS)
        and not any(k in _msg_lower for k in _REPORT_KEYWORDS)
        and _intake_complete
        # Make sure the message actually contains the intake info (not a random sentence
        # that happens to match old stored data)
        and _intake_fields_mentioned
    )

    if _is_intake_only:
        logger.info("chat_id={} intake fast-path: name={} age={} gender={}", chat_id, _pi_name, _pi_age, _pi_gender)

        # Persist patient info immediately
        _intake_pipeline: dict = {
            "patient_info": merged_patient_info,
            "pending_report_actor_role": None,
        }
        if _existing_mongo_patient_id:
            _intake_pipeline["mongo_patient_id"] = _existing_mongo_patient_id
        try:
            await chat_store.save_pipeline_state(chat_id, _intake_pipeline)
        except Exception:
            pass

        # Build acknowledgment
        _gender_str = _pi_gender.lower()
        _pronoun = "his" if _gender_str == "male" else "her" if _gender_str == "female" else "their"
        if actor_role == "doctor":
            _ack = (
                f"✅ Got it! Patient details saved:\n\n"
                f"- **Name:** {_pi_name}\n"
                f"- **Age:** {_pi_age}\n"
                f"- **Gender:** {_pi_gender.capitalize()}\n"
                + (f"- **Patient ID:** `{_existing_mongo_patient_id}`\n" if _existing_mongo_patient_id else "")
                + f"\nNow please **upload the X-ray image** and I'll begin the orthopedic analysis for {_pronoun} case."
            )
        else:
            _ack = (
                f"✅ Thanks! I've noted your details:\n\n"
                f"- **Name:** {_pi_name}\n"
                f"- **Age:** {_pi_age}\n"
                f"- **Gender:** {_pi_gender.capitalize()}\n"
                + (f"- **Patient ID:** `{_existing_mongo_patient_id}`\n" if _existing_mongo_patient_id else "")
                + "\n"
                f"Now please **upload your X-ray image** and I'll analyse it for you!"
            )

        _ack_msg_id = str(uuid4())
        await chat_store.append_message(
            chat_id=chat_id,
            message_id=_ack_msg_id,
            sender_role="assistant",
            content=_ack,
        )
        return AgentResponse(
            chat_id=chat_id,
            message_id=_ack_msg_id,
            session_id=chat_id,
            final_response=_ack,
            agent_trace=[],
        )
    # ── End fast-path ──────────────────────────────────────────────────────────

    payload = {
        "session_id": chat_id,
        "user_message": message,
        "messages": _history_to_langchain_messages(history_before, message),
        "image_data": image_data,
        "volume_path": volume_path,
        "dicom_metadata": dicom_metadata,
        "modality": modality,
        "body_region": body_region,
        "patient_id": _existing_mongo_patient_id or session.get("patient_id") or request.patient_id,
        "location": request.location,
        "actor_role": actor_role,
        "actor_name": clean_actor_name or "",
        "patient_info": merged_patient_info,
        # Re-inject clinical pipeline state from previous turns so the agent has context
        **pipeline_state,
    }

    logger.info("chat_id={} invoking agent", chat_id)
    request_timeout_seconds = _chat_timeout_seconds(volume_path=volume_path, modality=modality)
    try:
        result = await asyncio.wait_for(
            run_agent(payload),
            timeout=request_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning("chat_id={} agent timed out after {}s", chat_id, request_timeout_seconds)
        if volume_path or modality in {"ct", "mri"}:
            raise HTTPException(
                status_code=504,
                detail=(
                    "Volumetric CT/MRI analysis timed out. On first run the backend may still be downloading "
                    "segmentation model weights, and CPU inference can take several minutes. Please retry or increase "
                    "VOLUMETRIC_CHAT_TIMEOUT_SECONDS."
                ),
            )
        raise HTTPException(status_code=504, detail="Chat request timed out.")
    except AgentExecutionError as exc:
        raise HTTPException(status_code=500, detail=_agent_error_message(str(exc))) from exc

    detections = result.get("detections")
    # Only annotate when the user actually uploaded a fresh image this turn
    annotated_image_base64 = await _build_annotated_image(image_data, detections) if fresh_image else None
    final_response = result.get("final_response") or "No response generated."
    assistant_message_id = str(uuid4())
    trace = result.get("agent_trace") or []
    _tool_calls_this_turn = [str(name) for name in (result.get("tool_calls_made") or [])]
    _analysis_generated_this_turn = any(
        name in {"clinical_generate_diagnosis", "clinical_assess_triage"}
        for name in _tool_calls_this_turn
    )

    # ── Persist updated clinical pipeline state back to session ──────────────
    new_pipeline: dict = {}
    for _k in ("diagnosis", "triage_result", "body_part", "detections", "image_data", "volume_path", "dicom_metadata", "modality", "body_region"):
        _v = result.get(_k)
        if _v is not None:
            new_pipeline[_k] = _v
    # Track pending_report flag (None means clear it)
    _pending = result.get("pending_report_actor_role")
    new_pipeline["pending_report_actor_role"] = _pending  # explicit None clears it in MongoDB via $set
    # Merge patient_info: stored + newly extracted, always keep the most complete version
    result_pi = result.get("patient_info") or {}
    best_pi = {**stored_patient_info, **{k: v for k, v in merged_patient_info.items() if v}, **{k: v for k, v in result_pi.items() if v}}
    if _existing_mongo_patient_id:
        best_pi["patient_id"] = _existing_mongo_patient_id
    if best_pi:
        new_pipeline["patient_info"] = best_pi

    # ── Upsert patient record in MongoDB once all 3 intake fields are present ──
    _pi_complete = (
        bool(str(best_pi.get("name") or "").strip())
        and best_pi.get("age") is not None
        and bool(str(best_pi.get("gender") or "").strip())
    )
    if _pi_complete and mongo_service.enabled:
        try:
            _upserted = await patient_store.upsert_patient(
                name=str(best_pi["name"]),
                age=int(best_pi["age"]) if best_pi.get("age") is not None else None,
                gender=str(best_pi.get("gender") or ""),
                doctor_user_id=request.actor_id if actor_role == "doctor" else None,
                patient_user_id=request.actor_id if actor_role == "patient" else None,
                chat_id=chat_id,
                existing_patient_id=_existing_mongo_patient_id,
            )
            _mongo_patient_id: str = _upserted["patient_id"]
            _existing_mongo_patient_id = _mongo_patient_id
            new_pipeline["mongo_patient_id"] = _mongo_patient_id
            best_pi["patient_id"] = _mongo_patient_id
            new_pipeline["patient_info"] = best_pi
            logger.info("chat_id={} patient upserted patient_id={}", chat_id, _mongo_patient_id)
        except Exception as _pe:
            logger.warning("chat_id={} patient upsert failed: {}", chat_id, _pe)

    # Save analysis only when analysis tools ran in THIS turn (not report-only turns).
    if _analysis_generated_this_turn and mongo_service.enabled:
        _analysis_patient_id = str(new_pipeline.get("mongo_patient_id") or _existing_mongo_patient_id or "")
        _diag = result.get("diagnosis")
        _tria = result.get("triage_result")
        if _analysis_patient_id and _diag and _tria:
            try:
                await patient_store.add_analysis(
                    _analysis_patient_id,
                    {
                        "body_part": result.get("body_part"),
                        "diagnosis": _diag,
                        "triage": _tria,
                        "detections": result.get("detections"),
                    },
                )
            except Exception as _ae:
                logger.warning("chat_id={} failed to add analysis to patient: {}", chat_id, _ae)

    if new_pipeline:
        try:
            await chat_store.save_pipeline_state(chat_id, new_pipeline)
        except Exception:
            pass

    report_requested_this_turn = _report_requested(request.message)

    # Prefer the graph-generated report, but explicitly requested reports should
    # still complete even if the graph fails to emit a report URL.
    report_url = result.get("report_url") if isinstance(result.get("report_url"), str) else None
    report_error: str | None = None
    if not report_url and report_requested_this_turn:
        fallback_url, report_error = await _ensure_report(
            report_requested=True,
            actor_role=actor_role,
            diagnosis=result.get("diagnosis"),
            triage=result.get("triage_result"),
            patient_info=best_pi,
            image_base64=image_data,
            detections=result.get("detections") if isinstance(result.get("detections"), list) else None,
            annotated_image_base64=annotated_image_base64,
        )
        if fallback_url:
            report_url = fallback_url
            result["report_url"] = fallback_url
            logger.info("chat_id={} report generated via direct fallback", chat_id)

    # ── Save report to MongoDB when PDF was generated ─────────────────────────
    if report_url and mongo_service.enabled:
        try:
            _rpt_patient_id = str(
                best_pi.get("patient_id")
                or new_pipeline.get("mongo_patient_id")
                or _existing_mongo_patient_id
                or session.get("patient_id")
                or request.actor_id
            )
            _rpt_name = str(best_pi.get("name") or "Unknown")
            _rpt_severity = str((result.get("triage_result") or {}).get("level") or "GREEN")
            _rpt_body = str(result.get("body_part") or "").capitalize()
            _rpt_title = f"{_rpt_body} X-ray Analysis Report".strip() if _rpt_body else "Orthopedic Analysis Report"
            await patient_store.save_report(
                patient_id=_rpt_patient_id,
                patient_name=_rpt_name,
                pdf_url=report_url,
                title=_rpt_title,
                severity=_rpt_severity,
                doctor_user_id=request.actor_id if actor_role == "doctor" else None,
            )
            logger.info("chat_id={} report saved to MongoDB patient_id={}", chat_id, _rpt_patient_id)
        except Exception as _re:
            logger.warning("chat_id={} report MongoDB save failed: {}", chat_id, _re)

    if report_url:
        try:
            await chat_store.save_pipeline_state(chat_id, {"report_url": report_url})
        except Exception:
            pass

    if report_url and report_url not in final_response:
        final_response = f"{final_response}\n\nReport: {report_url}"
    elif report_requested_this_turn and report_error:
        final_response = f"{final_response}\n\n{report_error}"

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
        attachments=request.attachments,
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
