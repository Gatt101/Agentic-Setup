from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas.requests import ReportSaveRequest
from api.schemas.responses import ReportRetrieveResponse, ReportSaveResponse
from core.exceptions import StorageError
from services.storage import storage_service


router = APIRouter(tags=["reports"])


@router.post("/reports", response_model=ReportSaveResponse)
async def save_report(request: ReportSaveRequest) -> ReportSaveResponse:
    result = await storage_service.save_report(
        report_data=request.report_data,
        patient_id=request.patient_id,
        report_type=request.report_type,
    )
    return ReportSaveResponse(**result)


@router.get("/reports/{report_id}", response_model=ReportRetrieveResponse)
async def get_report(report_id: str) -> ReportRetrieveResponse:
    try:
        payload = await storage_service.retrieve_report(report_id)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ReportRetrieveResponse(
        report_data=payload.get("report_data", {}),
        pdf_url=payload.get("pdf_url"),
        created_at=payload.get("created_at"),
    )
