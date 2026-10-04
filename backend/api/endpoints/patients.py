"""Patients API — real data from MongoDB."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from core.auth import AuthenticatedActor, require_doctor
from services.patient_store import patient_store
from services.storage import storage_service

router = APIRouter(tags=["patients"])


def _to_iso(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def _triage_to_risk(triage: dict | None) -> str:
    """Map triage level to PatientRecord riskLevel."""
    if not triage:
        return "GREEN"
    level = str(triage.get("level") or triage.get("triage_level") or "GREEN").upper()
    if level in ("RED",):
        return "RED"
    if level in ("AMBER", "ORANGE", "YELLOW"):
        return "AMBER"
    return "GREEN"


def _latest_analysis_summary(analyses: list[dict]) -> tuple[str, str]:
    """Return (summary_text, last_study_date) from analyses list."""
    if not analyses:
        return "No analysis on record.", ""
    latest = analyses[-1]
    dx = latest.get("diagnosis") or {}
    body_part = str(latest.get("body_part") or dx.get("body_part") or "").capitalize()
    finding = dx.get("primary_diagnosis") or dx.get("finding") or "Pending review."
    summary = f"{body_part} — {finding}".strip(" —")
    date_raw = latest.get("created_at") or ""
    date_str = date_raw[:10] if date_raw else ""
    return summary, date_str


@router.get("/patients")
async def list_patients(
    actor: AuthenticatedActor = Depends(require_doctor),
) -> list[dict[str, Any]]:
    try:
        raw = await patient_store.list_by_doctor(actor.user_id, include_analyses=True)
    except RuntimeError as exc:
        logger.warning("patients list: MongoDB not available — {}", exc)
        return []

    results = []
    for p in raw:
        analyses: list[dict] = p.get("analyses") or []
        triage = (analyses[-1].get("triage") if analyses else None)
        summary, last_study = _latest_analysis_summary(analyses)
        risk = _triage_to_risk(triage)
        results.append(
            {
                "id": p.get("patient_id") or "",
                "name": p.get("name") or "Unknown",
                "age": p.get("age") or 0,
                "gender": p.get("gender") or "",
                "riskLevel": risk,
                "summary": summary,
                "lastStudy": last_study,
            }
        )
    return results


@router.get("/patients/{patient_id}")
async def get_patient(
    patient_id: str,
    actor: AuthenticatedActor = Depends(require_doctor),
) -> dict[str, Any]:
    try:
        patient = await patient_store.get_patient(patient_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    if patient.get("doctor_user_id") != actor.user_id:
        raise HTTPException(status_code=403, detail="Case belongs to another doctor.")
    patient.pop("_id", None)
    return patient


@router.delete("/patients/{patient_id}")
async def delete_patient(
    patient_id: str,
    actor: AuthenticatedActor = Depends(require_doctor),
) -> dict[str, Any]:
    try:
        patient = await patient_store.get_patient(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found.")
        if patient.get("doctor_user_id") != actor.user_id:
            raise HTTPException(status_code=403, detail="Case belongs to another doctor.")
        result = await patient_store.delete_patient(
            patient_id=patient_id,
            actor_id=actor.user_id,
            actor_role="doctor",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if int(result.get("deleted_patients", 0)) == 0:
        raise HTTPException(status_code=404, detail="Patient not found.")

    file_references = result.pop("file_references", [])
    deleted_files = 0
    for reference in file_references:
        if await storage_service.delete_reference(reference):
            deleted_files += 1
        path = storage_service.resolve_private_path(reference)
        if path and path.suffix.lower() == ".pdf":
            report_json = f"reports/{path.stem}.json"
            if await storage_service.delete_reference(report_json):
                deleted_files += 1

    return {"status": "ok", **result, "deleted_files": deleted_files}
