from __future__ import annotations

from langchain_core.tools import tool


def _severity_to_score(severity: str) -> float:
    mapping = {"mild": 0.4, "moderate": 0.65, "severe": 0.9}
    return mapping.get(severity.lower(), 0.5)


def _study_score(study: dict) -> float:
    report_data = study.get("report_data", {})
    diagnosis = report_data.get("diagnosis", {})
    if isinstance(diagnosis, dict) and "confidence" in diagnosis:
        return float(diagnosis["confidence"])
    if isinstance(diagnosis, dict):
        return _severity_to_score(str(diagnosis.get("severity", "moderate")))
    return 0.5


async def analyze_multiple_studies_impl(studies: list[dict], patient_id: str) -> dict:
    """Assess longitudinal progression across prior studies."""
    if len(studies) < 2:
        return {
            "longitudinal_analysis": "Not enough prior studies to establish trend.",
            "trend": "insufficient_data",
            "deterioration_flag": False,
            "recommendations": ["Collect at least one follow-up study for trend analysis."],
        }

    chronological = list(reversed(studies))
    scores = [_study_score(study) for study in chronological]
    delta = scores[-1] - scores[0]

    if delta > 0.1:
        trend = "worsening"
    elif delta < -0.1:
        trend = "improving"
    else:
        trend = "stable"

    deterioration = trend == "worsening"
    recommendations = [
        "Review with orthopedic specialist.",
        "Correlate imaging trend with physical exam findings.",
    ]
    if deterioration:
        recommendations.append("Consider expedited follow-up imaging and advanced intervention planning.")

    return {
        "longitudinal_analysis": (
            f"Patient {patient_id} has {len(studies)} studies. Trend appears {trend} "
            f"(score delta {delta:.2f})."
        ),
        "trend": trend,
        "deterioration_flag": deterioration,
        "recommendations": recommendations,
    }


@tool("clinical_analyze_multiple_studies")
async def analyze_multiple_studies(studies: list[dict], patient_id: str) -> dict:
    """Analyze longitudinal trends across multiple imaging studies."""
    return await analyze_multiple_studies_impl(studies, patient_id)


__all__ = ["analyze_multiple_studies", "analyze_multiple_studies_impl"]
