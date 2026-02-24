from __future__ import annotations

import base64
import binascii
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from api.schemas.requests import ChatRequest
from api.schemas.responses import AgentResponse
from core.exceptions import AgentExecutionError
from graph.graph import run_agent
from tools.utils import strip_data_url


router = APIRouter(tags=["chat"])


def _is_document_attachment(attachment: str | None) -> bool:
    if not attachment:
        return False

    normalized = attachment.strip().lower()
    if normalized.startswith("data:application/pdf"):
        return True
    if normalized.startswith("data:application/msword"):
        return True
    if normalized.startswith("data:application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        return True

    payload = strip_data_url(attachment)
    try:
        raw = base64.b64decode(payload, validate=False)
    except (ValueError, binascii.Error):
        return False

    return raw.startswith(b"%PDF")


@router.post("/chat", response_model=AgentResponse)
async def chat_with_agent(request: ChatRequest) -> AgentResponse:
    session_id = request.session_id or str(uuid4())
    attachment = request.attachment
    message = request.message
    image_data = attachment

    if _is_document_attachment(attachment):
        image_data = None
        message = (
            f"{request.message}\n\n"
            "[Attachment note: a document (PDF/DOC) was uploaded. "
            "Current vision analysis supports image uploads (JPG/PNG) only. "
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
        result = await run_agent(payload)
    except AgentExecutionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return AgentResponse(
        session_id=session_id,
        final_response=result.get("final_response") or "No response generated.",
        body_part=result.get("body_part"),
        diagnosis=result.get("diagnosis"),
        triage=result.get("triage_result"),
        hospitals=result.get("hospitals"),
        report_url=result.get("report_url"),
    )
