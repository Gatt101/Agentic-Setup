from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import SimpleITK as sitk


TOTAL_SEGMENTATOR_LABEL_MAP: dict[str, str] = {}

APPENDICULAR_LABEL_MAP: dict[str, str] = {}


def parse_segmentation_output(
    seg_dir: str | Path,
    label_map: dict[str, str] | None = None,
    spacing: tuple[float, ...] | None = None,
) -> list[dict[str, Any]]:
    seg_path = Path(seg_dir)
    if not seg_path.exists():
        return []

    findings: list[dict[str, Any]] = []

    for nifti_file in sorted(seg_path.glob("*.nii.gz")):
        image = sitk.ReadImage(str(nifti_file))
        arr = sitk.GetArrayFromImage(image)
        vox_spacing = spacing or image.GetSpacing()
        label_key = nifti_file.name.replace(".nii.gz", "")
        label_name = (label_map or {}).get(label_key, label_key)
        mask = arr > 0
        voxel_count = int(mask.sum())
        if voxel_count == 0:
            continue

        if vox_spacing:
            voxel_volume = vox_spacing[0] * vox_spacing[1] * vox_spacing[2]
            volume_mm3 = voxel_count * voxel_volume
        else:
            volume_mm3 = voxel_count

        slice_indices = np.where(mask.any(axis=(1, 2)))[0]
        slice_range = [int(slice_indices.min()), int(slice_indices.max())] if len(slice_indices) > 0 else []

        location: dict[str, Any] = {"label_key": label_key}
        if "vertebra" in label_name.lower():
            import re
            vert_match = re.search(r"([A-Z]\d+|S\d+)", label_name, re.IGNORECASE)
            if vert_match:
                location["vertebra"] = vert_match.group(1).upper()
        if "left" in label_name.lower():
            location["side"] = "left"
        elif "right" in label_name.lower():
            location["side"] = "right"

        findings.append({
            "label": label_name,
            "score": 1.0,
            "volume_mm3": round(volume_mm3, 1),
            "voxel_count": voxel_count,
            "location": location,
            "slice_range": slice_range,
        })

    findings.sort(key=lambda f: f.get("volume_mm3", 0), reverse=True)
    return findings


def extract_annotated_slices(
    seg_dir: str | Path,
    volume_path: str | Path | None = None,
    max_slices: int = 6,
) -> list[str]:
    seg_path = Path(seg_dir)
    nifti_files = list(seg_path.glob("*.nii.gz"))
    if not nifti_files:
        return []

    seg_image = sitk.ReadImage(str(nifti_files[0]))
    seg_arr = sitk.GetArrayFromImage(seg_image)

    if volume_path and Path(volume_path).exists():
        orig_image = sitk.ReadImage(str(volume_path))
        orig_arr = sitk.GetArrayFromImage(orig_image)
    else:
        orig_arr = seg_arr

    unique_labels = np.unique(seg_arr)
    unique_labels = unique_labels[unique_labels > 0]

    if len(unique_labels) == 0:
        return []

    slices_with_content = []
    for slice_idx in range(seg_arr.shape[0]):
        label_count = len(np.unique(seg_arr[slice_idx])) - 1
        if label_count > 0:
            slices_with_content.append((slice_idx, label_count))

    slices_with_content.sort(key=lambda x: x[1], reverse=True)

    selected_indices = []
    total = len(slices_with_content)
    if total <= max_slices:
        selected_indices = [s[0] for s in slices_with_content]
    else:
        step = max(1, total // max_slices)
        selected_indices = [slices_with_content[i * step][0] for i in range(max_slices)]

    annotated_slices = []
    for idx in sorted(selected_indices):
        orig_slice = orig_arr[idx].astype(np.float32)
        seg_slice = seg_arr[idx]

        orig_min = orig_slice.min()
        orig_max = orig_slice.max()
        if orig_max - orig_min > 0:
            orig_norm = ((orig_slice - orig_min) / (orig_max - orig_min) * 255).astype(np.uint8)
        else:
            orig_norm = np.zeros_like(orig_slice, dtype=np.uint8)

        rgb = np.stack([orig_norm, orig_norm, orig_norm], axis=-1)

        label_colors = {
            1: [255, 0, 0],
            2: [0, 255, 0],
            3: [0, 0, 255],
            4: [255, 255, 0],
            5: [255, 0, 255],
            6: [0, 255, 255],
            7: [255, 128, 0],
            8: [128, 0, 255],
        }

        for label_val in unique_labels:
            mask = seg_slice == label_val
            color = label_colors.get(int(label_val) % len(label_colors), [255, 0, 0])
            rgb[mask, 0] = color[0]
            rgb[mask, 1] = color[1]
            rgb[mask, 2] = color[2]

        from PIL import Image
        from io import BytesIO
        import base64

        pil_img = Image.fromarray(rgb, mode="RGB")
        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        annotated_slices.append(f"data:image/png;base64,{b64}")

    return annotated_slices
