from __future__ import annotations

import shutil

import SimpleITK as sitk
from langchain_core.tools import tool
from loguru import logger

from tools.ct.ct_utils import extract_annotated_slices, parse_segmentation_output
from tools.mri.mri_runtime import run_totalsegmentator_mri


MRI_VERTEBRAE_LABEL_MAP = {
    1: "vertebra_S1",
    2: "vertebra_L5",
    3: "vertebra_L4",
    4: "vertebra_L3",
    5: "vertebra_L2",
    6: "vertebra_L1",
    7: "vertebra_T12",
    8: "vertebra_T11",
    9: "vertebra_T10",
    10: "vertebra_T9",
    11: "vertebra_T8",
    12: "vertebra_T7",
    13: "vertebra_T6",
    14: "vertebra_T5",
    15: "vertebra_T4",
    16: "vertebra_T3",
    17: "vertebra_T2",
    18: "vertebra_T1",
    19: "vertebra_C7",
    20: "vertebra_C6",
    21: "vertebra_C5",
    22: "vertebra_C4",
    23: "vertebra_C3",
    24: "vertebra_C2",
    25: "vertebra_C1",
}


@tool("mri_analyze_spine")
async def mri_analyze_spine_impl(volume_path: str) -> dict:
    """Analyze spine MRI using TotalSegmentator vertebrae_mr task.

    Segments vertebrae C1 through S1 from MRI data.
    """
    logger.info("Starting spine MRI analysis: {}", volume_path)

    result = await run_totalsegmentator_mri(volume_path, task="vertebrae_mr", device="cpu", fast=True)

    if "error" in result:
        return {"findings": [], "summary": {"error": result["error"]}, "annotated_slices_base64": []}

    output_dir = result.get("output_dir", "")

    try:
        spacing = sitk.ReadImage(volume_path).GetSpacing()
    except Exception:
        spacing = None

    findings = parse_segmentation_output(output_dir, label_map=MRI_VERTEBRAE_LABEL_MAP, spacing=spacing)
    annotated = extract_annotated_slices(output_dir, volume_path=volume_path, max_slices=8)

    vertebrae = [f for f in findings if "vertebra" in f.get("label", "")]
    affected = [f.get("location", {}).get("vertebra", "") for f in vertebrae if f.get("location", {}).get("vertebra")]

    summary = {
        "total_vertebrae": len(vertebrae),
        "affected_vertebrae": affected,
        "regions_analyzed": ["spine"],
        "task": "vertebrae_mr",
        "model": "TotalSegmentator",
    }

    shutil.rmtree(output_dir, ignore_errors=True)

    return {
        "findings": findings,
        "summary": summary,
        "annotated_slices_base64": annotated,
    }


__all__ = ["mri_analyze_spine_impl"]
