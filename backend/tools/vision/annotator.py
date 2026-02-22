from __future__ import annotations

from typing import Any

from PIL import ImageDraw
from langchain_core.tools import tool

from tools.utils import decode_image_base64, encode_image_base64


def _bbox_to_pixels(bbox: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    if len(bbox) != 4:
        return (0, 0, width - 1, height - 1)
    x1, y1, x2, y2 = bbox
    if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.0:
        x1 *= width
        x2 *= width
        y1 *= height
        y2 *= height
    return int(x1), int(y1), int(x2), int(y2)


async def annotate_xray_image_impl(image_base64: str, detections: list[dict[str, Any]]) -> dict:
    """Draw detection boxes and labels on an X-ray image."""
    image = decode_image_base64(image_base64)
    width, height = image.size
    canvas = ImageDraw.Draw(image)

    for idx, detection in enumerate(detections, start=1):
        bbox = detection.get("bbox") or detection.get("box") or [0.1, 0.1, 0.9, 0.9]
        label = detection.get("label", f"finding_{idx}")
        score = detection.get("score", 0.0)
        x1, y1, x2, y2 = _bbox_to_pixels(bbox, width, height)
        canvas.rectangle([x1, y1, x2, y2], outline=(255, 0, 0), width=3)
        canvas.text((x1 + 4, max(0, y1 - 18)), f"{label} ({score:.2f})", fill=(255, 0, 0))

    return {"annotated_image_base64": encode_image_base64(image)}


@tool("vision_annotate_xray_image")
async def annotate_xray_image(image_base64: str, detections: list[dict[str, Any]]) -> dict:
    """Annotate X-ray image with model detections."""
    return await annotate_xray_image_impl(image_base64, detections)


__all__ = ["annotate_xray_image", "annotate_xray_image_impl"]
