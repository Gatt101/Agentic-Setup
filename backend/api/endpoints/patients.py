"""Patients API — real data from MongoDB."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from services.patient_store import patient_store

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
    actor_id: str = Query(..., description="Clerk user ID"),
    actor_role: str = Query(..., description="doctor or patient"),
) -> list[dict[str, Any]]:
    role = actor_role.strip().lower()
    if role not in ("doctor", "patient"):
        raise HTTPException(status_code=400, detail="actor_role must be 'doctor' or 'patient'.")

    try:
        if role == "doctor":
            raw = await patient_store.list_by_doctor(actor_id)
        else:
            raw = await patient_store.list_by_patient_user(actor_id)
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
async def get_patient(patient_id: str) -> dict[str, Any]:
    try:
        patient = await patient_store.get_patient(patient_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    patient.pop("_id", None)
    return patient
