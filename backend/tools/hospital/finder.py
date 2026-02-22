from __future__ import annotations

from langchain_core.tools import tool

from tools.hospital.data import HOSPITALS


def _score_hospital(item: dict, location: str, urgency: str, specialty: str) -> float:
    score = item.get("rating", 0.0)
    loc = location.lower().strip()
    specialty_key = specialty.lower().strip()
    urgency_key = urgency.upper().strip()

    if loc and loc in item.get("location", ""):
        score += 1.0
    if specialty_key and specialty_key in " ".join(item.get("services", [])).lower():
        score += 0.8
    if urgency_key == "RED" and item.get("er_available"):
        score += 1.2
    return score


async def find_nearby_hospitals_impl(location: str, urgency: str, specialty: str) -> dict:
    ranked = sorted(
        HOSPITALS,
        key=lambda item: _score_hospital(item, location, urgency, specialty),
        reverse=True,
    )
    return {
        "hospitals": ranked,
        "ranked_by_relevance": True,
        "count": len(ranked),
    }


@tool("hospital_find_nearby_hospitals")
async def find_nearby_hospitals(location: str, urgency: str, specialty: str) -> dict:
    """Find and rank nearby hospitals based on urgency and specialty."""
    return await find_nearby_hospitals_impl(location, urgency, specialty)


__all__ = ["find_nearby_hospitals", "find_nearby_hospitals_impl"]
