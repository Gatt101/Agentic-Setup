from __future__ import annotations

from langchain_core.tools import tool


async def analyze_patient_symptoms_impl(symptoms: str, body_part: str, age: int) -> dict:
    """Extract risk factors and red flags from free-text symptoms."""
    text = (symptoms or "").lower()

    risk_factors: list[str] = []
    if age >= 65:
        risk_factors.append("age-related bone fragility risk")
    if "osteoporosis" in text:
        risk_factors.append("known osteoporosis history")
    if "fall" in text:
        risk_factors.append("fall-related trauma mechanism")

    possible_conditions = [f"{body_part} fracture" if body_part else "fracture"]
    if "swelling" in text:
        possible_conditions.append("soft tissue injury")
    if "numb" in text or "tingling" in text:
        possible_conditions.append("neurovascular compromise")

    red_flags: list[str] = []
    for keyword, description in {
        "open": "possible open fracture",
        "deform": "visible deformity",
        "cannot move": "loss of function",
        "cold": "possible distal perfusion issue",
    }.items():
        if keyword in text:
            red_flags.append(description)

    return {
        "risk_factors": risk_factors,
        "possible_conditions": possible_conditions,
        "red_flags": red_flags,
    }


@tool("clinical_analyze_patient_symptoms")
async def analyze_patient_symptoms(symptoms: str, body_part: str, age: int) -> dict:
    """Analyze symptom text for risk factors and warning signs."""
    return await analyze_patient_symptoms_impl(symptoms, body_part, age)


__all__ = ["analyze_patient_symptoms", "analyze_patient_symptoms_impl"]
