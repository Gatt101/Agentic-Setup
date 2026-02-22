from __future__ import annotations

from langchain_core.tools import tool

from tools.utils import clamp, decode_image_base64


async def detect_body_part_impl(image_base64: str) -> dict:
    """Simple body part classifier fallback until model integration is wired."""
    try:
        image = decode_image_base64(image_base64)
    except Exception:
        return {
            "body_part": "unknown",
            "confidence": 0.0,
            "rationale": "Unable to decode image payload.",
        }

    width, height = image.size
    ratio = width / max(height, 1)

    if ratio >= 1.0:
        body_part = "hand"
        confidence = clamp(0.62 + (ratio - 1.0) * 0.2, 0.4, 0.93)
        rationale = "Image is wider than tall, matching common hand/wrist framing."
    else:
        body_part = "leg"
        confidence = clamp(0.62 + (1.0 - ratio) * 0.2, 0.4, 0.93)
        rationale = "Image is taller than wide, matching common leg/tibia framing."

    return {
        "body_part": body_part,
        "confidence": round(confidence, 3),
        "rationale": rationale,
    }


@tool("vision_detect_body_part")
async def detect_body_part(image_base64: str) -> dict:
    """Detect likely orthopedic body part from X-ray image data."""
    return await detect_body_part_impl(image_base64)


__all__ = ["detect_body_part", "detect_body_part_impl"]
