from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from api.schemas.requests import AnalyzeRequest
from api.schemas.responses import AgentResponse
from core.exceptions import AgentExecutionError
from graph.graph import run_agent
from tools.vision.annotator import annotate_xray_image_impl


router = APIRouter(tags=["analysis"])


async def _build_annotated_image(image_data: str | None, detections: object) -> str | None:
    if not image_data or not isinstance(detections, list):
        return None
    try:
        payload = await annotate_xray_image_impl(image_data, detections)
    except Exception:
        return None
    encoded = payload.get("annotated_image_base64")
    return encoded if isinstance(encoded, str) and encoded else None


@router.post("/analyze", response_model=AgentResponse)
async def analyze_xray(request: AnalyzeRequest) -> AgentResponse:
    session_id = request.session_id or str(uuid4())
    user_message = request.user_message or request.symptoms or "Analyze this X-ray."

    payload = {
        "session_id": session_id,
        "user_message": user_message,
        "image_data": request.image_data,
        "symptoms": request.symptoms,
        "patient_id": request.patient_id,
        "location": request.location,
    }

    try:
        result = await run_agent(payload)
    except AgentExecutionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    detections = result.get("detections")
    annotated_image_base64 = await _build_annotated_image(request.image_data, detections)

    return AgentResponse(
        session_id=session_id,
        final_response=result.get("final_response") or "No response generated.",
        body_part=result.get("body_part"),
        diagnosis=result.get("diagnosis"),
        triage=result.get("triage_result"),
        hospitals=result.get("hospitals"),
        report_url=result.get("report_url"),
        annotated_image_base64=annotated_image_base64,
        agent_trace=result.get("agent_trace"),
    )
