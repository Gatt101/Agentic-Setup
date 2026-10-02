from __future__ import annotations

import base64
import binascii
from io import BytesIO

from PIL import Image

from core.config import settings


MAX_XRAY_PIXELS = 64_000_000
ALLOWED_XRAY_FORMATS = {"JPEG", "PNG"}
ALLOWED_XRAY_MIME_TYPES = {"image/jpeg", "image/png"}


def strip_data_url(value: str) -> str:
    if "," in value and value.strip().startswith("data:"):
        return value.split(",", 1)[1]
    return value


def validate_xray_base64(image_base64: str) -> bytes:
    value = str(image_base64 or "").strip()
    if not value or value.startswith(("http://", "https://", "/")):
        raise ValueError("X-ray must be an uploaded PNG or JPEG image.")

    if value.startswith("data:"):
        if "," not in value:
            raise ValueError("Malformed image data URL.")
        header, payload = value.split(",", 1)
        mime_type = header[5:].split(";", 1)[0].lower()
        if mime_type not in ALLOWED_XRAY_MIME_TYPES or ";base64" not in header.lower():
            raise ValueError("Only base64-encoded PNG and JPEG images are supported.")
    else:
        payload = value

    max_encoded_length = ((settings.max_xray_bytes + 2) // 3) * 4 + 8
    if len(payload) > max_encoded_length:
        raise ValueError(f"X-ray exceeds the {settings.max_xray_mb} MiB upload limit.")

    try:
        image_bytes = base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Image payload is not valid base64.") from exc
    if len(image_bytes) > settings.max_xray_bytes:
        raise ValueError(f"X-ray exceeds the {settings.max_xray_mb} MiB upload limit.")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = str(image.format or "").upper()
            width, height = image.size
            image.verify()
    except Exception as exc:
        raise ValueError("Uploaded file is not a valid image.") from exc

    if image_format not in ALLOWED_XRAY_FORMATS:
        raise ValueError("Only PNG and JPEG images are supported.")
    if width <= 0 or height <= 0 or width * height > MAX_XRAY_PIXELS:
        raise ValueError("Image dimensions exceed the 64-megapixel limit.")
    return image_bytes


def decode_image_base64(image_base64: str) -> Image.Image:
    image_bytes = validate_xray_base64(image_base64)
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
