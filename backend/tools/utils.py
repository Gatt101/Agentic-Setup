from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image


def strip_data_url(value: str) -> str:
    if "," in value and value.strip().startswith("data:"):
        return value.split(",", 1)[1]
    return value


def decode_image_base64(image_base64: str) -> Image.Image:
    payload = strip_data_url(image_base64)
    image_bytes = base64.b64decode(payload)
    return Image.open(BytesIO(image_bytes)).convert("RGB")


def encode_image_base64(image: Image.Image, image_format: str = "PNG") -> str:
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def decode_dicom_base64(dicom_base64: str) -> bytes:
    payload = strip_data_url(dicom_base64)
    return base64.b64decode(payload)


def is_dicom_data(data: bytes) -> bool:
    if len(data) < 132:
        return False
    return data[128:132] == b"DICM"
