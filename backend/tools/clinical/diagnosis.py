from __future__ import annotations

from langchain_core.tools import tool


def _format_label(label: str) -> str:
    return label.replace("_", " ").strip() if label else "possible fracture"


def _looks_like_pathology(label: str) -> bool:
    text = (label or "").lower()
    pathology_keywords = (
        "fracture",
        "tear",
        "lesion",
        "compression",
        "dislocation",
        "herniation",
        "stenosis",
        "effusion",
        "bruise",
    )
    return any(keyword in text for keyword in pathology_keywords)


async def generate_diagnosis_impl(detections: list[dict], symptoms: str, body_part: str) -> dict:
    """Generate a structured diagnostic summary from detections and symptoms."""
    if not detections:
        return {
            "finding": f"No confident fracture detected in {body_part or 'the submitted region'}",
            "severity": "mild",
            "patient_summary": "No high-confidence fracture marker was detected. Correlate with clinical exam.",
            "confidence": 0.35,
        }

    top_detection = max(detections, key=lambda item: float(item.get("score", 0.0)))
    label = _format_label(str(top_detection.get("label", "possible fracture")))
    confidence = float(top_detection.get("score", 0.0))

    if not _looks_like_pathology(label):
        confidence = min(confidence, 0.45)
        summary = (
            f"Automated imaging analysis identified structural anatomy in the {body_part or 'imaged area'} "
            f"with no explicit pathology label. Symptoms noted: {symptoms}. "
            f"Correlate with formal radiology review and clinical examination."
        ).strip()
        return {
            "finding": f"Automated structural analysis completed for {body_part or 'the submitted region'}",
            "severity": "mild",
            "patient_summary": summary,
            "confidence": round(confidence, 3),
        }

    if confidence >= 0.8:
        severity = "severe"
    elif confidence >= 0.6:
        severity = "moderate"
    else:
        severity = "mild"

    symptom_phrase = f"Symptoms noted: {symptoms}. " if symptoms else ""
    summary = (
        f"Likely {label} affecting the {body_part or 'imaged area'} with {severity} severity. "
        f"{symptom_phrase}Clinical confirmation by a licensed physician is required."
    )

    return {
        "finding": label,
        "severity": severity,
        "patient_summary": summary.strip(),
        "confidence": round(confidence, 3),
    }


@tool("clinical_generate_diagnosis")
async def generate_diagnosis(detections: list[dict], symptoms: str, body_part: str) -> dict:
    """Create diagnosis output from fracture detections and symptoms."""
    return await generate_diagnosis_impl(detections, symptoms, body_part)


__all__ = ["generate_diagnosis", "generate_diagnosis_impl"]
