from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Any

from ultralytics import YOLO

from core.config import settings
from tools.utils import clamp, decode_image_base64


class YoloRuntimeError(RuntimeError):
    """Raised when YOLO runtime cannot load models or run inference."""


def _load_model(model_path: Path) -> YOLO:
    if not model_path.exists():
        raise YoloRuntimeError(f"Model file not found: {model_path}")
    return YOLO(str(model_path))


@lru_cache(maxsize=1)
def get_hand_model() -> YOLO:
    return _load_model(settings.resolved_hand_model_path)


@lru_cache(maxsize=1)
def get_leg_model() -> YOLO:
    return _load_model(settings.resolved_leg_model_path)


def _format_yolo_output(result: Any) -> tuple[list[dict[str, Any]], dict[str, float], list[list[float]]]:
    names = result.names or {}
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return [], {}, []

    width = float(result.orig_shape[1])
    height = float(result.orig_shape[0])
    detections: list[dict[str, Any]] = []
    confidence_map: dict[str, float] = {}
    raw_boxes: list[list[float]] = []

    for idx in range(len(boxes)):
        box = boxes[idx]
        score = float(box.conf[0]) if box.conf is not None else 0.0
        class_id = int(box.cls[0]) if box.cls is not None else -1
        label = str(names.get(class_id, f"class_{class_id}"))
        xyxy = box.xyxy[0].tolist() if box.xyxy is not None else [0.0, 0.0, width, height]
        raw_boxes.append([round(float(value), 2) for value in xyxy])

        normalized = [
            clamp(float(xyxy[0]) / max(width, 1.0), 0.0, 1.0),
            clamp(float(xyxy[1]) / max(height, 1.0), 0.0, 1.0),
            clamp(float(xyxy[2]) / max(width, 1.0), 0.0, 1.0),
            clamp(float(xyxy[3]) / max(height, 1.0), 0.0, 1.0),
        ]

        detection = {
            "label": label,
            "score": round(score, 4),
            "bbox": [round(value, 4) for value in normalized],
        }
        detections.append(detection)
        confidence_map[label] = max(confidence_map.get(label, 0.0), detection["score"])

    return detections, confidence_map, raw_boxes


def _predict_sync(model: YOLO, image_base64: str, threshold: float) -> dict[str, Any]:
    image = decode_image_base64(image_base64)
    prediction = model.predict(
        source=image,
        conf=max(threshold, settings.detector_score_min),
        iou=settings.nms_iou,
        verbose=False,
        device="cpu",
    )
    result = prediction[0]
    detections, confidence_map, raw_boxes = _format_yolo_output(result)
    return {
        "detections": detections,
        "confidence_map": confidence_map,
        "raw_boxes": raw_boxes,
    }


async def run_hand_model(image_base64: str, threshold: float) -> dict[str, Any]:
    model = get_hand_model()
    return await asyncio.to_thread(_predict_sync, model, image_base64, threshold)


async def run_leg_model(image_base64: str, threshold: float) -> dict[str, Any]:
    model = get_leg_model()
    return await asyncio.to_thread(_predict_sync, model, image_base64, threshold)


def max_detection_confidence(payload: dict[str, Any]) -> float:
    detections = payload.get("detections", [])
    if not detections:
        return 0.0
    return max(float(item.get("score", 0.0)) for item in detections)
