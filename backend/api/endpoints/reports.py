from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from api.schemas.requests import ReportSaveRequest
from api.schemas.responses import ReportRetrieveResponse, ReportSaveResponse
from core.exceptions import StorageError
from services.patient_store import patient_store
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


@router.get("/reports/list")
async def list_reports(
    actor_id: str = Query(..., description="Clerk user ID"),
    actor_role: str = Query(..., description="doctor or patient"),
    patient_id: str | None = Query(None),
) -> list[dict[str, Any]]:
    """List reports from MongoDB for the current user."""
    role = actor_role.strip().lower()
    if role not in ("doctor", "patient"):
        raise HTTPException(status_code=400, detail="actor_role must be 'doctor' or 'patient'.")

    try:
        if role == "doctor":
            raw = await patient_store.list_reports_by_doctor(actor_id)
        else:
            # For patient role, find their patient record first then list reports
            raw_patients = await patient_store.list_by_patient_user(actor_id)
            resolved_pid = patient_id or (raw_patients[0].get("patient_id") if raw_patients else None)
            raw = await patient_store.list_reports_by_patient_id(resolved_pid) if resolved_pid else []
    except RuntimeError as exc:
        logger.warning("reports list: MongoDB not available — {}", exc)
        return []

    results = []
    for r in raw:
        results.append(
            {
                "id": r.get("report_id") or "",
                "patientName": r.get("patient_name") or "Unknown",
                "title": r.get("title") or "Orthopedic Report",
                "severity": r.get("severity") or "GREEN",
                "status": r.get("status") or "finalized",
                "pdfUrl": r.get("pdf_url"),
                "createdAt": r["created_at"].isoformat() if hasattr(r.get("created_at"), "isoformat") else str(r.get("created_at") or ""),
            }
        )
    return results


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
