from __future__ import annotations

from langchain_core.tools import tool

from tools.modality.dicom_utils import is_dicom, normalize_body_part, read_dicom_metadata


@tool("modality_parse_dicom")
async def parse_dicom_impl(dicom_bytes_b64: str) -> dict:
    """Parse a DICOM file from base64-encoded bytes and return metadata."""
    import base64
    from io import BytesIO

    try:
        raw = base64.b64decode(dicom_bytes_b64)
    except Exception as exc:
        return {"error": f"Failed to decode base64: {exc}", "modality": "unknown", "body_part": "unknown"}

    if not is_dicom(raw):
        return {"error": "Not a valid DICOM file", "modality": "unknown", "body_part": "unknown"}

    try:
        metadata = read_dicom_metadata(raw)
    except Exception as exc:
        return {"error": f"Failed to parse DICOM metadata: {exc}", "modality": "unknown", "body_part": "unknown"}

    body_part = normalize_body_part(
        metadata.get("body_part_examined", ""),
        metadata.get("study_description", ""),
        metadata.get("series_description", ""),
    )

    return {
        "modality": metadata.get("modality", "unknown"),
        "body_part": body_part,
        "metadata": metadata,
    }


@tool("modality_extract_mid_slice")
async def extract_mid_slice_impl(nifti_path: str) -> dict:
    """Extract the middle axial slice from a 3D NIfTI volume as a base64 PNG."""
    import SimpleITK as sitk
    import numpy as np
    from PIL import Image
    from io import BytesIO

    try:
        image = sitk.ReadImage(nifti_path)
        arr = sitk.GetArrayFromImage(image)
    except Exception as exc:
        return {"error": f"Failed to read volume: {exc}", "mid_slice_base64": None}

    if arr.ndim != 3:
        return {"error": f"Expected 3D volume, got {arr.ndim}D", "mid_slice_base64": None}

    mid_idx = arr.shape[0] // 2
    slice_2d = arr[mid_idx]

    slice_min = float(slice_2d.min())
    slice_max = float(slice_2d.max())
    if slice_max - slice_min > 0:
        slice_norm = ((slice_2d - slice_min) / (slice_max - slice_min) * 255).astype(np.uint8)
    else:
        slice_norm = np.zeros_like(slice_2d, dtype=np.uint8)

    pil_image = Image.fromarray(slice_norm, mode="L").convert("RGB")
    buffer = BytesIO()
    pil_image.save(buffer, format="PNG")
    import base64
    b64_str = base64.b64encode(buffer.getvalue()).decode("ascii")

    return {
        "mid_slice_base64": f"data:image/png;base64,{b64_str}",
        "slice_index": mid_idx,
        "total_slices": arr.shape[0],
        "slice_shape": list(slice_2d.shape),
    }


__all__ = ["parse_dicom_impl", "extract_mid_slice_impl"]
