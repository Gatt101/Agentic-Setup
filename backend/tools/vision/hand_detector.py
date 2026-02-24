from __future__ import annotations

from langchain_core.tools import tool

from tools.vision.yolo_runtime import run_hand_model


async def detect_hand_fracture_impl(image_base64: str, threshold: float = 0.35) -> dict:
    """Detect hand/wrist fractures using the configured YOLO model."""
    try:
        return await run_hand_model(image_base64, threshold)
    except Exception:
        return {"detections": [], "confidence_map": {}, "raw_boxes": []}


@tool("vision_detect_hand_fracture")
async def detect_hand_fracture(image_base64: str, threshold: float = 0.35) -> dict:
    """Detect likely hand/wrist fracture regions from X-ray image data."""
    return await detect_hand_fracture_impl(image_base64, threshold)


__all__ = ["detect_hand_fracture", "detect_hand_fracture_impl"]
