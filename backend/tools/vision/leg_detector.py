from __future__ import annotations

from langchain_core.tools import tool

from tools.vision.yolo_runtime import run_leg_model


async def detect_leg_fracture_impl(image_base64: str, threshold: float = 0.35) -> dict:
    """Detect leg fractures using the configured YOLO model."""
    try:
        return await run_leg_model(image_base64, threshold)
    except Exception:
        return {"detections": [], "confidence_map": {}, "raw_boxes": []}


@tool("vision_detect_leg_fracture")
async def detect_leg_fracture(image_base64: str, threshold: float = 0.35) -> dict:
    """Detect likely leg fracture regions from X-ray image data."""
    return await detect_leg_fracture_impl(image_base64, threshold)


__all__ = ["detect_leg_fracture", "detect_leg_fracture_impl"]
