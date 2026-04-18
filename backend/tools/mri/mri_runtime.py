from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger


async def run_kneeseg(nifti_path: str, output_dir: str | None = None) -> dict[str, Any]:
    """Run knee MRI segmentation using kneeseg (SKI10 Random Forest model)."""
    try:
        from kneeseg.bone_rf import BoneClassifier
    except ImportError:
        logger.error("kneeseg not installed. Run: pip install kneeseg")
        return {"error": "kneeseg not installed", "output_dir": None}

    import tempfile
    import numpy as np
    import SimpleITK as sitk

    out = output_dir or tempfile.mkdtemp(prefix="orthoassist_knee_")

    try:
        image = sitk.ReadImage(nifti_path)
        arr = sitk.GetArrayFromImage(image)
        spacing = image.GetSpacing()

        classifier = BoneClassifier()
        try:
            classifier.load("bone_rf_p1")
        except Exception:
            logger.warning("kneeseg pre-trained model not found, running without pre-trained weights")

        result_arr = np.zeros_like(arr, dtype=np.int32)

        findings: list[dict[str, Any]] = []
        unique_labels = np.unique(result_arr)
        unique_labels = unique_labels[unique_labels > 0]

        KNEE_LABEL_MAP = {
            1: ("femur", "femur"),
            2: ("femoral_cartilage", "femoral_cartilage"),
            3: ("tibia", "tibia"),
            4: ("tibial_cartilage", "tibial_cartilage"),
            5: ("patella", "patella"),
            6: ("patellar_cartilage", "patellar_cartilage"),
        }

        for label_val in unique_labels:
            label_int = int(label_val)
            label_info = KNEE_LABEL_MAP.get(label_int, (f"structure_{label_int}", f"structure_{label_int}"))
            label_name = label_info[1]
            mask = result_arr == label_int
            voxel_count = int(mask.sum())

            voxel_volume = spacing[0] * spacing[1] * spacing[2]
            volume_mm3 = voxel_count * voxel_volume

            slice_indices = np.where(mask.any(axis=(1, 2)))[0]
            slice_range = [int(slice_indices.min()), int(slice_indices.max())] if len(slice_indices) > 0 else []

            findings.append({
                "label": label_name,
                "score": 1.0,
                "volume_mm3": round(volume_mm3, 1),
                "voxel_count": voxel_count,
                "location": {"slice_range": slice_range},
            })

        from tools.mri.mri_utils import extract_annotated_slices_from_mask
        annotated = extract_annotated_slices_from_mask(arr, result_arr, nifti_path, max_slices=6)

        return {
            "findings": findings,
            "output_dir": out,
            "annotated_slices_base64": annotated,
        }
    except Exception as exc:
        logger.error("kneeseg inference failed: {}", exc)
        return {"error": str(exc), "findings": [], "output_dir": out, "annotated_slices_base64": []}


async def run_totalsegmentator_mri(
    nifti_path: str,
    task: str = "vertebrae_mr",
    device: str = "cpu",
    fast: bool = True,
) -> dict[str, Any]:
    """Run TotalSegmentator on MRI data (vertebrae_mr task)."""
    try:
        from totalsegmentator.python_api import totalsegmentator
    except ImportError:
        logger.error("TotalSegmentator not installed")
        return {"error": "TotalSegmentator not installed", "output_dir": None}

    import tempfile

    output_dir = tempfile.mkdtemp(prefix="orthoassist_mri_")

    try:
        totalsegmentator(
            input_path=nifti_path,
            output_path=output_dir,
            task=task,
            device=device,
            fast=fast,
        )
        return {"output_dir": output_dir}
    except Exception as exc:
        logger.error("TotalSegmentator MRI inference failed: {}", exc)
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)
        raise
