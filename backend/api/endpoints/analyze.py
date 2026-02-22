from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from api.schemas.requests import AnalyzeRequest
from api.schemas.responses import AgentResponse
from core.exceptions import AgentExecutionError
from graph.graph import run_agent


router = APIRouter(tags=["analysis"])


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

    return AgentResponse(
        session_id=session_id,
        final_response=result.get("final_response") or "No response generated.",
        body_part=result.get("body_part"),
        diagnosis=result.get("diagnosis"),
        triage=result.get("triage_result"),
        hospitals=result.get("hospitals"),
        report_url=result.get("report_url"),
    )
