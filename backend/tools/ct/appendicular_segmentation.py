from __future__ import annotations

import shutil

import SimpleITK as sitk
from langchain_core.tools import tool
from loguru import logger

from tools.ct.ct_runtime import run_totalsegmentator
from tools.ct.ct_utils import APPENDICULAR_LABEL_MAP, extract_annotated_slices, parse_segmentation_output


@tool("ct_analyze_appendicular")
async def ct_analyze_appendicular_impl(volume_path: str) -> dict:
    """Analyze appendicular skeleton CT for foot, ankle, hand, wrist, knee, and elbow bones.

    Uses TotalSegmentator appendicular_bones task for detailed peripheral skeleton segmentation.
    """
    logger.info("Starting appendicular bones CT analysis: {}", volume_path)

    result = await run_totalsegmentator(
        nifti_path=volume_path,
        task="appendicular_bones",
        device="cpu",
        fast=True,
    )

    if "error" in result:
        return {"findings": [], "summary": {"error": result["error"]}, "annotated_slices_base64": []}

    output_dir = result.get("output_dir", "")

    try:
        spacing = sitk.ReadImage(volume_path).GetSpacing()
    except Exception:
        spacing = None

    findings = parse_segmentation_output(output_dir, label_map=APPENDICULAR_LABEL_MAP, spacing=spacing)
    annotated = extract_annotated_slices(output_dir, volume_path=volume_path, max_slices=6)

    regions = set()
    for f in findings:
        label = f.get("label", "").lower()
        if any(b in label for b in ["tarsal", "metatarsal", "phalanges_feet", "patella", "tibia", "fibula"]):
            regions.add("foot")
        if any(b in label for b in ["carpal", "metacarpal", "phalanges_hand", "radius", "ulna"]):
            regions.add("hand")

    summary = {
        "total_structures": len(findings),
        "regions_analyzed": sorted(regions),
        "task": "appendicular_bones",
        "model": "TotalSegmentator",
    }

    shutil.rmtree(output_dir, ignore_errors=True)

    return {
        "findings": findings,
        "summary": summary,
        "annotated_slices_base64": annotated,
    }


__all__ = ["ct_analyze_appendicular_impl"]
