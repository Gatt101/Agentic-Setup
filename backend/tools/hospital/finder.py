from __future__ import annotations

import httpx
from langchain_core.tools import tool
from loguru import logger

from core.config import settings
from tools.hospital.data import HOSPITALS

_SERP_URL = "https://serpapi.com/search"
_SERP_TIMEOUT = 10  # seconds


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


def _static_fallback(location: str, urgency: str, specialty: str) -> dict:
    ranked = sorted(
        HOSPITALS,
        key=lambda item: _score_hospital(item, location, urgency, specialty),
        reverse=True,
    )
    return {"hospitals": ranked, "ranked_by_relevance": True, "count": len(ranked), "source": "static"}


def _parse_serp_results(data: dict, urgency: str) -> list[dict]:
    """Convert SerpAPI Google Maps response into our hospital schema."""
    hospitals = []
    for place in data.get("local_results", []):
        name = place.get("title", "")
        if not name:
            continue
        address = place.get("address", "")
        phone = place.get("phone", "")
        rating = float(place.get("rating") or 0.0)
        place_type = str(place.get("type", "")).lower()
        er_available = any(kw in place_type for kw in ("emergency", "trauma", "er"))

        # Infer services from type string
        services: list[str] = []
        if "orthop" in place_type or "orthop" in name.lower():
            services.append("orthopedics")
        if "emergency" in place_type or er_available:
            services.append("emergency")
        if "rehab" in place_type:
            services.append("rehabilitation")
        if not services:
            services.append("general medicine")

        hospitals.append({
            "name": name,
            "address": address,
            "phone": phone,
            "rating": rating,
            "er_available": er_available,
            "services": services,
            "source": "serp",
        })
    return hospitals


async def _serp_hospital_search(location: str, urgency: str, specialty: str) -> dict | None:
    """Call SerpAPI Google Maps and return parsed results, or None on any error."""
    api_key = settings.serp_api_key
    if not api_key:
        return None

    query = f"orthopedic hospital near {location}"
    if urgency.upper() == "RED":
        query = f"emergency orthopedic hospital near {location}"
    elif specialty:
        query = f"{specialty} hospital near {location}"

    params = {
        "engine": "google_maps",
        "q": query,
        "type": "search",
        "api_key": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=_SERP_TIMEOUT) as client:
            resp = await client.get(_SERP_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("SerpAPI hospital search failed (location={}): {}", location, exc)
        return None

    hospitals = _parse_serp_results(data, urgency)
    if not hospitals:
        logger.info("SerpAPI returned no results for location={}, using static fallback", location)
        return None

    # Sort: ER first for RED triage, then by rating
    if urgency.upper() == "RED":
        hospitals.sort(key=lambda h: (not h["er_available"], -h["rating"]))
    else:
        hospitals.sort(key=lambda h: -h["rating"])

    logger.info("SerpAPI returned {} hospitals for location={}", len(hospitals), location)
    return {"hospitals": hospitals, "ranked_by_relevance": True, "count": len(hospitals), "source": "serp"}


async def find_nearby_hospitals_impl(location: str, urgency: str, specialty: str) -> dict:
    # Try real SerpAPI search first; fall back to static dataset on failure
    result = await _serp_hospital_search(location, urgency, specialty)
    if result:
        return result
    return _static_fallback(location, urgency, specialty)


@tool("hospital_find_nearby_hospitals")
async def find_nearby_hospitals(location: str, urgency: str, specialty: str) -> dict:
    """Find and rank nearby hospitals based on location, urgency and specialty using live search."""
    return await find_nearby_hospitals_impl(location, urgency, specialty)


__all__ = ["find_nearby_hospitals", "find_nearby_hospitals_impl"]
