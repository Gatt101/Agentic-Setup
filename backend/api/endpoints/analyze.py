from __future__ import annotations

import base64
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from api.schemas.requests import AnalyzeRequest
from api.schemas.responses import AgentResponse
from core.config import settings
from core.exceptions import AgentExecutionError
from tools.modality.dicom_utils import (
    dicom_bytes_to_nifti_file,
    is_dicom,
    normalize_body_part,
    read_dicom_metadata,
)
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


def _decode_base64_payload(payload: str) -> bytes:
    body = payload.split(",", 1)[1] if payload.strip().startswith("data:") and "," in payload else payload
    return base64.b64decode(body)


@router.post("/analyze", response_model=AgentResponse)
async def analyze_xray(request: AnalyzeRequest) -> AgentResponse:
    from graph.graph import run_agent

    session_id = request.session_id or str(uuid4())
    modality = request.modality
    body_region = request.body_region
    image_data = request.image_data
    volume_path: str | None = None
    dicom_metadata: dict | None = None

    if request.dicom_data:
        try:
            dicom_bytes = _decode_base64_payload(request.dicom_data)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid dicom_data payload: {exc}") from exc

        if not is_dicom(dicom_bytes):
            raise HTTPException(status_code=400, detail="dicom_data is not a valid DICOM payload")

        try:
            dicom_metadata = read_dicom_metadata(dicom_bytes)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to read DICOM metadata: {exc}") from exc

        modality = modality or dicom_metadata.get("modality")
        body_region = body_region or normalize_body_part(
            str(dicom_metadata.get("body_part_examined") or ""),
            str(dicom_metadata.get("study_description") or ""),
            str(dicom_metadata.get("series_description") or ""),
        )

        settings.dicom_storage_path.mkdir(parents=True, exist_ok=True)
        settings.nifti_storage_path.mkdir(parents=True, exist_ok=True)
        dicom_path = settings.dicom_storage_path / f"{session_id}.dcm"
        nifti_path = settings.nifti_storage_path / f"{session_id}.nii.gz"
        dicom_path.write_bytes(dicom_bytes)
        volume_path, volume_info = dicom_bytes_to_nifti_file(dicom_bytes, str(nifti_path))
        dicom_metadata = {**dicom_metadata, **volume_info}

    if not modality:
        modality = "xray" if image_data else None

    default_prompt = "Analyze this imaging study." if modality in {"ct", "mri"} else "Analyze this X-ray."
    user_message = request.user_message or request.symptoms or default_prompt

    payload = {
        "session_id": session_id,
        "user_message": user_message,
        "image_data": image_data,
        "modality": modality,
        "body_region": body_region,
        "volume_path": volume_path,
        "dicom_metadata": dicom_metadata,
        "symptoms": request.symptoms,
        "patient_id": request.patient_id,
        "location": request.location,
    }

    try:
        result = await run_agent(payload)
    except AgentExecutionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    detections = result.get("detections")
    annotated_image_base64 = await _build_annotated_image(image_data, detections)

    return AgentResponse(
        session_id=session_id,
        final_response=result.get("final_response") or "No response generated.",
        modality=result.get("modality") or modality,
        body_region=result.get("body_region") or body_region,
        body_part=result.get("body_part"),
        diagnosis=result.get("diagnosis"),
        triage=result.get("triage_result"),
        hospitals=result.get("hospitals"),
        report_url=result.get("report_url"),
        annotated_image_base64=annotated_image_base64,
        annotated_slices_base64=result.get("annotated_slices_base64"),
        agent_trace=result.get("agent_trace"),
    )
