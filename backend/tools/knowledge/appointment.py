from __future__ import annotations

from langchain_core.tools import tool

_FOLLOWUP_SCHEDULE = {
    "RED": {
        "initial_review_days": 1,
        "initial_review_note": "Emergency department or specialist review within 24 hours",
        "milestones": [
            {"week": 1, "visit": "Post-operative / post-ER wound check"},
            {"week": 2, "visit": "Wound healing and cast/fixation review"},
            {"week": 6, "visit": "Radiographic healing assessment"},
            {"week": 12, "visit": "Functional assessment and rehabilitation review"},
            {"week": 24, "visit": "Final orthopaedic discharge / return-to-activity clearance"},
        ],
        "imaging_schedule": [
            {"week": 0, "scan": "Baseline X-ray (already taken)"},
            {"week": 6, "scan": "Follow-up X-ray to confirm callus formation"},
            {"week": 12, "scan": "Final X-ray for union confirmation"},
        ],
    },
    "AMBER": {
        "initial_review_days": 4,
        "initial_review_note": "Urgent care or GP review within 3–5 days",
        "milestones": [
            {"week": 1, "visit": "Splint / cast check and pain review"},
            {"week": 4, "visit": "Radiographic healing progress"},
            {"week": 8, "visit": "Functional assessment and physio review"},
            {"week": 12, "visit": "Discharge or further plan if needed"},
        ],
        "imaging_schedule": [
            {"week": 0, "scan": "Baseline X-ray (already taken)"},
            {"week": 4, "scan": "Follow-up X-ray to check alignment"},
            {"week": 8, "scan": "Healing confirmation X-ray"},
        ],
    },
    "GREEN": {
        "initial_review_days": 14,
        "initial_review_note": "GP follow-up in 2 weeks or sooner if symptoms worsen",
        "milestones": [
            {"week": 2, "visit": "Symptom review and progress check"},
            {"week": 6, "visit": "Functional assessment and return-to-activity decision"},
        ],
        "imaging_schedule": [
            {"week": 0, "scan": "Baseline X-ray (already taken)"},
            {"week": 6, "scan": "X-ray only if not clinically improved"},
        ],
    },
}

_SPECIALIST_REFERRAL = {
    "RED": "Immediate orthopaedic surgeon referral required.",
    "AMBER": "Orthopaedic or fracture clinic referral within 1 week.",
    "GREEN": "GP management; refer to orthopaedics only if not healing by week 6.",
}

_PHYSIO_START = {
    "RED": "Physiotherapy to begin after surgical clearance (typically week 3–4).",
    "AMBER": "Physiotherapy to begin at week 2 once acute pain subsides.",
    "GREEN": "Self-guided exercises from day 2; formal physio if not improving by week 3.",
}


async def get_appointment_schedule_impl(
    diagnosis: str,
    triage_level: str,
    body_part: str = "",
    patient_age: int = 40,
) -> dict:
    level = triage_level.strip().upper()
    schedule = _FOLLOWUP_SCHEDULE.get(level, _FOLLOWUP_SCHEDULE["AMBER"])

    age_adjustment = ""
    if patient_age >= 65:
        age_adjustment = (
            "Senior patients: add bone density appointment at week 6 and "
            "falls-prevention assessment within 2 weeks."
        )
    elif patient_age < 18:
        age_adjustment = (
            "Paediatric patient: ensure paediatric orthopaedic review is included "
            "at the week-6 appointment to monitor growth plate."
        )

    location_phrase = f" ({body_part})" if body_part else ""

    return {
        "diagnosis": diagnosis + location_phrase,
        "triage_level": level,
        "initial_review": {
            "days_from_now": schedule["initial_review_days"],
            "note": schedule["initial_review_note"],
        },
        "follow_up_milestones": schedule["milestones"],
        "imaging_schedule": schedule["imaging_schedule"],
        "specialist_referral": _SPECIALIST_REFERRAL.get(level, _SPECIALIST_REFERRAL["AMBER"]),
        "physiotherapy_start": _PHYSIO_START.get(level, _PHYSIO_START["AMBER"]),
        "age_specific_adjustment": age_adjustment,
        "general_advice": (
            "Attend all scheduled appointments even if you feel better. "
            "Contact the clinic early if pain worsens, numbness develops, or the cast feels tight."
        ),
    }


@tool("knowledge_get_appointment_schedule")
async def get_appointment_schedule(
    diagnosis: str,
    triage_level: str,
    body_part: str = "",
    patient_age: int = 40,
) -> dict:
    """Generate a follow-up appointment and imaging schedule based on injury severity and triage level."""
    return await get_appointment_schedule_impl(diagnosis, triage_level, body_part, patient_age)


__all__ = ["get_appointment_schedule", "get_appointment_schedule_impl"]
