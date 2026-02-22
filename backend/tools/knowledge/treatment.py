from __future__ import annotations

from langchain_core.tools import tool


async def get_treatment_recommendations_impl(diagnosis: str, triage_level: str, patient_age: int) -> dict:
    level = triage_level.strip().upper()
    immediate_steps = ["Immobilize affected limb", "Avoid weight bearing until reassessment"]
    long_term = ["Orthopedic follow-up", "Guided physiotherapy"]
    medications = ["Acetaminophen or NSAID if clinically appropriate"]
    restrictions = ["No high-impact activity", "No unsupervised splint removal"]

    if level == "RED":
        immediate_steps = ["Call emergency services", "Transport to nearest ER", "Keep patient NPO until reviewed"]
        medications.append("Emergency analgesia per physician protocol")
    elif level == "AMBER":
        immediate_steps.append("Present to urgent care within 6-12 hours")

    if patient_age >= 65:
        long_term.append("Bone density assessment and fall prevention counseling")

    return {
        "immediate_steps": immediate_steps,
        "long_term": long_term,
        "medications": medications,
        "restrictions": restrictions,
        "diagnosis_context": diagnosis,
    }


@tool("knowledge_get_treatment_recommendations")
async def get_treatment_recommendations(diagnosis: str, triage_level: str, patient_age: int) -> dict:
    """Provide treatment recommendations based on diagnosis and urgency."""
    return await get_treatment_recommendations_impl(diagnosis, triage_level, patient_age)


__all__ = ["get_treatment_recommendations", "get_treatment_recommendations_impl"]
