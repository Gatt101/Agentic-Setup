from __future__ import annotations

from langchain_core.tools import tool


@tool("modality_detect_imaging_modality")
async def detect_imaging_modality_impl(
    image_data: str | None = None,
    dicom_bytes_b64: str | None = None,
) -> dict:
    """Detect the imaging modality (X-ray, CT, or MRI) from uploaded data.

    Uses DICOM metadata when available, otherwise falls back to image heuristics.
    """
    if dicom_bytes_b64:
        import base64

        try:
            raw = base64.b64decode(dicom_bytes_b64)
        except Exception as exc:
            return {"modality": "unknown", "confidence": 0.0, "rationale": f"Failed to decode base64: {exc}"}

        from tools.modality.dicom_utils import is_dicom, read_dicom_metadata, normalize_body_part

        if is_dicom(raw):
            try:
                metadata = read_dicom_metadata(raw)
                modality = metadata.get("modality", "unknown")
                body_part = normalize_body_part(
                    metadata.get("body_part_examined", ""),
                    metadata.get("study_description", ""),
                    metadata.get("series_description", ""),
                )
                confidence = 0.95 if modality != "unknown" else 0.3
                return {
                    "modality": modality,
                    "confidence": confidence,
                    "body_part_suggestion": body_part,
                    "rationale": f"Detected from DICOM Modality tag: {metadata.get('raw_modality_tag', modality)}",
                }
            except Exception as exc:
                return {"modality": "unknown", "confidence": 0.0, "rationale": f"DICOM parse error: {exc}"}

    if image_data:
        from tools.modality.dicom_utils import is_dicom
        import base64

        try:
            stripped = image_data.split(",", 1)[-1] if "," in image_data else image_data
            raw = base64.b64decode(stripped)
        except Exception:
            return {"modality": "unknown", "confidence": 0.0, "rationale": "Failed to decode image data"}

        if is_dicom(raw):
            from tools.modality.dicom_utils import read_dicom_metadata, normalize_body_part

            try:
                metadata = read_dicom_metadata(raw)
                modality = metadata.get("modality", "unknown")
                body_part = normalize_body_part(
                    metadata.get("body_part_examined", ""),
                    metadata.get("study_description", ""),
                    metadata.get("series_description", ""),
                )
                confidence = 0.95 if modality != "unknown" else 0.3
                return {
                    "modality": modality,
                    "confidence": confidence,
                    "body_part_suggestion": body_part,
                    "rationale": f"Detected from DICOM Modality tag in image_data: {metadata.get('raw_modality_tag', modality)}",
                }
            except Exception as exc:
                pass

        from tools.utils import decode_image_base64

        try:
            pil_image = decode_image_base64(image_data)
            w, h = pil_image.size
        except Exception:
            return {"modality": "unknown", "confidence": 0.0, "rationale": "Could not decode image"}

        if w >= 512 and h >= 512:
            return {
                "modality": "xray",
                "confidence": 0.70,
                "body_part_suggestion": "unknown",
                "rationale": "Large 2D image with no DICOM metadata, assumed X-ray.",
            }

        return {
            "modality": "xray",
            "confidence": 0.60,
            "body_part_suggestion": "unknown",
            "rationale": "2D image with no DICOM metadata, assumed X-ray.",
        }

    return {"modality": "unknown", "confidence": 0.0, "rationale": "No image or DICOM data provided"}


__all__ = ["detect_imaging_modality_impl"]
