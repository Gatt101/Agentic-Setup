from __future__ import annotations

from langchain_core.tools import tool

from core.config import settings
from tools.utils import clamp


def _severity_to_score(severity: str) -> float:
    mapping = {
        "severe": 0.9,
        "moderate": 0.7,
        "mild": 0.45,
    }
    return mapping.get(severity.lower(), 0.5)


def _timeframe(level: str) -> str:
    return {
        "RED": "Immediate emergency care",
        "AMBER": "Urgent care within 6-12 hours",
        "GREEN": "Outpatient follow-up within 24-72 hours",
    }[level]


async def assess_triage_impl(diagnosis: dict, detections: list[dict], patient_vitals: str) -> dict:
    """Assess urgency level from diagnosis plus additional context."""
    severity = str(diagnosis.get("severity", "moderate"))
    base_score = _severity_to_score(severity)
    max_detection = max((float(item.get("score", 0.0)) for item in detections), default=0.0)
    vitals_text = (patient_vitals or "").lower()

    danger_keywords = ["unconscious", "hypotension", "severe pain", "open fracture", "bleeding"]
    danger_bonus = 0.15 if any(key in vitals_text for key in danger_keywords) else 0.0

    urgency_score = clamp((base_score * 0.7) + (max_detection * 0.2) + danger_bonus, 0.0, 1.0)

    if urgency_score >= settings.triage_red_threshold:
        level = "RED"
    elif urgency_score >= settings.triage_amber_threshold:
        level = "AMBER"
    else:
        level = "GREEN"

    rationale = (
        f"Severity '{severity}' and detection confidence {max_detection:.2f} produced urgency score {urgency_score:.2f}."
    )
    if danger_bonus:
        rationale += " Vitals contain emergency risk indicators."

    return {
        "level": level,
        "rationale": rationale,
        "urgency_score": round(urgency_score, 3),
        "recommended_timeframe": _timeframe(level),
    }


@tool("clinical_assess_triage")
async def assess_triage(diagnosis: dict, detections: list[dict], patient_vitals: str) -> dict:
    """Classify patient urgency as RED, AMBER, or GREEN."""
    return await assess_triage_impl(diagnosis, detections, patient_vitals)


__all__ = ["assess_triage", "assess_triage_impl"]
