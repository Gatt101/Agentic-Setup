from __future__ import annotations

import asyncio

from langchain_core.tools import tool

from tools.utils import clamp, decode_image_base64
from tools.vision.yolo_runtime import max_detection_confidence, run_hand_model, run_leg_model


async def detect_body_part_impl(image_base64: str) -> dict:
    """Infer body part using model confidence, with ratio fallback."""
    try:
        hand_payload, leg_payload = await asyncio.gather(
            run_hand_model(image_base64, threshold=0.2),
            run_leg_model(image_base64, threshold=0.2),
        )
        hand_conf = max_detection_confidence(hand_payload)
        leg_conf = max_detection_confidence(leg_payload)
        if hand_conf > 0.0 or leg_conf > 0.0:
            if hand_conf >= leg_conf:
                return {
                    "body_part": "hand",
                    "confidence": round(hand_conf, 3),
                    "rationale": "Selected hand model based on higher detection confidence.",
                }
            return {
                "body_part": "leg",
                "confidence": round(leg_conf, 3),
                "rationale": "Selected leg model based on higher detection confidence.",
            }
    except Exception:
        pass

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
