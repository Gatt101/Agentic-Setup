from __future__ import annotations

import numpy as np
from PIL import Image
from io import BytesIO
import base64
import SimpleITK as sitk
from typing import Any


def extract_annotated_slices_from_mask(
    orig_arr: np.ndarray,
    seg_arr: np.ndarray,
    volume_path: str | None = None,
    max_slices: int = 6,
) -> list[str]:
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
    total = len(slices_with_content)

    if total <= max_slices:
        selected_indices = [s[0] for s in slices_with_content]
    else:
        step = max(1, total // max_slices)
        selected_indices = [slices_with_content[i * step][0] for i in range(max_slices)]

    MRI_COLORS = {
        1: [0, 128, 255],
        2: [255, 200, 0],
        3: [0, 200, 100],
        4: [200, 0, 200],
        5: [255, 100, 0],
        6: [0, 255, 200],
    }

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

        for label_val in unique_labels:
            mask = seg_slice == label_val
            color = MRI_COLORS.get(int(label_val) % len(MRI_COLORS), [0, 128, 255])
            rgb[mask, 0] = color[0]
            rgb[mask, 1] = color[1]
            rgb[mask, 2] = color[2]

        pil_img = Image.fromarray(rgb, mode="RGB")
        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        annotated_slices.append(f"data:image/png;base64,{b64}")

    return annotated_slices
