from __future__ import annotations

import asyncio
import base64
import binascii
import re
from uuid import uuid4

from fastapi import APIRouter

from api.schemas.requests import ChatRequest
from api.schemas.responses import AgentResponse
from core.config import settings
from core.exceptions import AgentExecutionError
from graph.graph import run_agent
from tools.utils import decode_image_base64, strip_data_url


router = APIRouter(tags=["chat"])


def _classify_attachment(attachment: str | None) -> str:
    """Return one of: none, image, document_or_other."""
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

    # Common non-image signatures.
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

    if "groq_api_key" in normalized or "api key" in normalized:
        return (
            "Backend LLM credentials are not configured correctly. "
            "Please verify server environment variables."
        )

    return (
        "I hit an internal processing issue and could not complete this request. "
        "Please retry in a moment."
    )


@router.post("/chat", response_model=AgentResponse)
async def chat_with_agent(request: ChatRequest) -> AgentResponse:
    session_id = request.session_id or str(uuid4())
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

    payload = {
        "session_id": session_id,
        "user_message": message,
        "image_data": image_data,
        "patient_id": request.patient_id,
        "location": request.location,
    }

    try:
        result = await asyncio.wait_for(
            run_agent(payload),
            timeout=max(5, settings.chat_request_timeout_seconds),
        )
    except asyncio.TimeoutError:
        return AgentResponse(
            session_id=session_id,
            final_response=(
                "The analysis is taking longer than expected. "
                "Please retry in a moment, or simplify the prompt/attachment."
            ),
            body_part=None,
            diagnosis=None,
            triage=None,
            hospitals=None,
            report_url=None,
        )
    except AgentExecutionError as exc:
        return AgentResponse(
            session_id=session_id,
            final_response=_agent_error_message(str(exc)),
            body_part=None,
            diagnosis=None,
            triage=None,
            hospitals=None,
            report_url=None,
        )

    return AgentResponse(
        session_id=session_id,
        final_response=result.get("final_response") or "No response generated.",
        body_part=result.get("body_part"),
        diagnosis=result.get("diagnosis"),
        triage=result.get("triage_result"),
        hospitals=result.get("hospitals"),
        report_url=result.get("report_url"),
    )
