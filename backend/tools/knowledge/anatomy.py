from __future__ import annotations

from langchain_core.tools import tool


_ANATOMY = {
    "hand": {
        "anatomy_info": "Hand anatomy includes carpal bones, metacarpals, and phalanges with dense neurovascular structures.",
        "common_injuries": ["distal radius fracture", "scaphoid fracture", "metacarpal fracture"],
        "xray_landmarks": ["radial styloid", "ulnar styloid", "scaphoid waist"],
    },
    "leg": {
        "anatomy_info": "Leg anatomy includes tibia and fibula with adjacent knee and ankle joint alignment considerations.",
        "common_injuries": ["tibial shaft fracture", "fibular fracture", "ankle malleolar fracture"],
        "xray_landmarks": ["tibial plateau", "fibular head", "distal tibiofibular syndesmosis"],
    },
}


async def get_anatomical_reference_impl(body_part: str, region: str) -> dict:
    data = _ANATOMY.get(body_part.strip().lower())
    if not data:
        return {
            "anatomy_info": f"No specific anatomy entry for {body_part} ({region}).",
            "common_injuries": ["contusion", "sprain", "fracture"],
            "xray_landmarks": ["joint line", "cortical outline"],
        }
    return data


@tool("knowledge_get_anatomical_reference")
async def get_anatomical_reference(body_part: str, region: str) -> dict:
    """Return anatomy-focused reference data for orthopedic interpretation."""
    return await get_anatomical_reference_impl(body_part, region)


__all__ = ["get_anatomical_reference", "get_anatomical_reference_impl"]
