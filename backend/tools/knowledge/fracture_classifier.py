from __future__ import annotations

from langchain_core.tools import tool


async def classify_fracture_type_impl(description: str, location: str, mechanism: str) -> dict:
    text = f"{description} {location} {mechanism}".lower()

    if "spiral" in text:
        fracture_type = "spiral"
        ao = "A1"
        severity = "moderate"
    elif "comminuted" in text:
        fracture_type = "comminuted"
        ao = "C2"
        severity = "severe"
    elif "transverse" in text:
        fracture_type = "transverse"
        ao = "A3"
        severity = "moderate"
    else:
        fracture_type = "undifferentiated"
        ao = "A0"
        severity = "mild"

    return {
        "fracture_type": fracture_type,
        "AO_classification": ao,
        "severity": severity,
        "notes": "Classification is heuristic and should be confirmed by radiology review.",
    }


@tool("knowledge_classify_fracture_type")
async def classify_fracture_type(description: str, location: str, mechanism: str) -> dict:
    """Classify likely fracture type and return AO-style code guidance."""
    return await classify_fracture_type_impl(description, location, mechanism)


__all__ = ["classify_fracture_type", "classify_fracture_type_impl"]
