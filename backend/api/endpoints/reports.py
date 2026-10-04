from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from loguru import logger

from api.schemas.responses import ReportRetrieveResponse
from core.auth import AuthenticatedActor, require_doctor
from core.exceptions import StorageError
from services.patient_store import patient_store
from services.storage import storage_service


router = APIRouter(tags=["reports"])


async def _get_owned_report(report_id: str, doctor_id: str) -> dict[str, Any]:
    try:
        report = await patient_store.get_report(report_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    if report.get("doctor_user_id") != doctor_id:
        raise HTTPException(status_code=403, detail="Report belongs to another doctor.")
    return report


@router.get("/reports/list")
async def list_reports(
    actor: AuthenticatedActor = Depends(require_doctor),
) -> list[dict[str, Any]]:
    """List reports from MongoDB for the current user."""
    try:
        raw = await patient_store.list_reports_by_doctor(actor.user_id)
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
                "status": r.get("status") or "draft",
                "pdfUrl": f"/api/reports/{r.get('report_id')}/pdf" if r.get("report_id") else None,
                "createdAt": r["created_at"].isoformat() if hasattr(r.get("created_at"), "isoformat") else str(r.get("created_at") or ""),
            }
        )
    return results


@router.get("/reports/{report_id}", response_model=ReportRetrieveResponse)
async def get_report(
    report_id: str,
    actor: AuthenticatedActor = Depends(require_doctor),
) -> ReportRetrieveResponse:
    report = await _get_owned_report(report_id, actor.user_id)

    reference = report.get("pdf_path") or report.get("pdf_url")
    report_path = storage_service.resolve_private_path(reference)
    source_id = report_path.stem if report_path else report_id
    try:
        payload = await storage_service.retrieve_report(source_id)
    except StorageError as exc:
        logger.warning("report metadata unavailable for {}: {}", report_id, exc)
        payload = {"report_data": report}

    return ReportRetrieveResponse(
        report_data=payload.get("report_data", {}),
        pdf_url=f"/api/reports/{report_id}/pdf",
        created_at=str(payload.get("created_at") or report.get("created_at") or ""),
    )


@router.get("/reports/{report_id}/pdf")
async def download_report_pdf(
    report_id: str,
    actor: AuthenticatedActor = Depends(require_doctor),
) -> FileResponse:
    report = await _get_owned_report(report_id, actor.user_id)

    reference = report.get("pdf_path") or report.get("pdf_url")
    path = storage_service.resolve_private_path(reference)
    if path is None or not path.is_file() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Report file not found.")

    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=f"{Path(report_id).name}.pdf",
    )
