from __future__ import annotations

from langchain_core.tools import tool


_PHASE_TEMPLATES = {
    "RED": {
        "phase_1": {"weeks": "0–2", "label": "Acute / Post-surgical", "activities": [
            "Complete rest and immobilization",
            "Ice 20 min every 2 hours for the first 48 h",
            "Keep limb elevated above heart level",
            "Pain management per physician prescription",
        ]},
        "phase_2": {"weeks": "3–6", "label": "Protective Mobilisation", "activities": [
            "Supervised passive range-of-motion exercises only",
            "Non-weight-bearing with crutches / walker",
            "Wound or cast care as directed",
            "Gentle breathing and circulation exercises",
        ]},
        "phase_3": {"weeks": "7–12", "label": "Active Rehabilitation", "activities": [
            "Graduated active-assisted range-of-motion",
            "Progressive partial weight-bearing",
            "Isometric muscle strengthening",
            "Hydrotherapy if cleared by surgeon",
        ]},
        "phase_4": {"weeks": "13+", "label": "Return to Function", "activities": [
            "Full weight-bearing training",
            "Functional strength and balance exercises",
            "Proprioception and coordination drills",
            "Gradual return to daily activities and low-impact sport",
        ]},
    },
    "AMBER": {
        "phase_1": {"weeks": "0–1", "label": "Rest & Protection", "activities": [
            "RICE: Rest, Ice, Compression, Elevation",
            "Splint / brace immobilisation",
            "OTC analgesia as needed",
        ]},
        "phase_2": {"weeks": "2–4", "label": "Early Mobilisation", "activities": [
            "Gentle range-of-motion within pain limits",
            "Partial weight-bearing as tolerated",
            "Supervised physiotherapy twice weekly",
        ]},
        "phase_3": {"weeks": "5–8", "label": "Strengthening", "activities": [
            "Progressive resistance exercises",
            "Balance and proprioception training",
            "Return to normal walking / activities of daily living",
        ]},
        "phase_4": {"weeks": "9+", "label": "Return to Activity", "activities": [
            "Sport-specific functional drills",
            "Full return to pre-injury activity",
            "Home exercise programme for maintenance",
        ]},
    },
    "GREEN": {
        "phase_1": {"weeks": "0–1", "label": "Immediate Care", "activities": [
            "RICE protocol for first 48 h",
            "Protective taping or soft splint",
        ]},
        "phase_2": {"weeks": "1–3", "label": "Restore Movement", "activities": [
            "Progressive range-of-motion exercises",
            "Gentle strengthening as pain allows",
        ]},
        "phase_3": {"weeks": "4–6", "label": "Functional Restoration", "activities": [
            "Full weight-bearing activities",
            "Functional strength training",
            "Return to normal daily activities",
        ]},
        "phase_4": {"weeks": "6+", "label": "Maintenance", "activities": [
            "Home exercise programme",
            "Monitor for recurrence",
        ]},
    },
}

_PRECAUTIONS_BY_AGE = {
    "elderly": [
        "Fall prevention assessment mandatory",
        "Bone density (DEXA) scan recommended",
        "Daily calcium and vitamin D supplementation",
        "Non-slip footwear and home hazard assessment",
    ],
    "paediatric": [
        "Monitor growth plate involvement with paediatric orthopaedist",
        "Activity restrictions tailored to developmental stage",
        "Parental supervision during exercises",
    ],
    "adult": [
        "Smoking cessation advised — delays bone healing",
        "Calcium-rich diet and adequate protein intake",
        "Avoid NSAIDs long-term without physician guidance",
    ],
}


async def get_rehabilitation_plan_impl(
    diagnosis: str,
    triage_level: str,
    patient_age: int,
    body_part: str = "",
) -> dict:
    level = triage_level.strip().upper()
    phases = _PHASE_TEMPLATES.get(level, _PHASE_TEMPLATES["AMBER"])

    if patient_age >= 65:
        age_group = "elderly"
    elif patient_age < 18:
        age_group = "paediatric"
    else:
        age_group = "adult"

    location_note = f" focusing on {body_part}" if body_part else ""

    return {
        "diagnosis": diagnosis,
        "triage_level": level,
        "patient_age": patient_age,
        "age_group": age_group,
        "rehabilitation_phases": phases,
        "special_precautions": _PRECAUTIONS_BY_AGE[age_group],
        "physiotherapy_frequency": "3× per week" if level == "RED" else "2× per week",
        "estimated_recovery_weeks": 16 if level == "RED" else (10 if level == "AMBER" else 6),
        "summary": (
            f"Structured {age_group} rehabilitation programme{location_note} "
            f"for {diagnosis}. Estimated recovery: "
            f"{'16' if level == 'RED' else ('10' if level == 'AMBER' else '6')} weeks."
        ),
    }


@tool("knowledge_get_rehabilitation_plan")
async def get_rehabilitation_plan(
    diagnosis: str,
    triage_level: str,
    patient_age: int,
    body_part: str = "",
) -> dict:
    """Generate a structured physiotherapy rehabilitation plan with phased recovery milestones."""
    return await get_rehabilitation_plan_impl(diagnosis, triage_level, patient_age, body_part)


__all__ = ["get_rehabilitation_plan", "get_rehabilitation_plan_impl"]
