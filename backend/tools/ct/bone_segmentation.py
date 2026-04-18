from __future__ import annotations

import shutil
from langchain_core.tools import tool
from loguru import logger

from tools.ct.ct_runtime import run_totalsegmentator
from tools.ct.ct_utils import TOTAL_SEGMENTATOR_LABEL_MAP, extract_annotated_slices, parse_segmentation_output


@tool("ct_analyze_full_body")
async def ct_analyze_full_body_impl(
    volume_path: str,
    roi_subset: str | None = None,
) -> dict:
    """Run full body CT bone segmentation using TotalSegmentator (117 classes).

    Detects all bones including femur, tibia, vertebrae, ribs, pelvis, spine, etc.
    """
    logger.info("Starting TotalSegmentator full body CT analysis: {}", volume_path)

    roi_list = roi_subset.split(",") if roi_subset else None

    result = await run_totalsegmentator(
        nifti_path=volume_path,
        task="total",
        device="cpu",
        fast=True,
        roi_subset=roi_list,
    )

    if "error" in result:
        return {"findings": [], "summary": {"error": result["error"]}, "annotated_slices_base64": []}

    output_dir = result.get("output_dir", "")

    import SimpleITK as sitk
    try:
        spacing = sitk.ReadImage(volume_path).GetSpacing()
    except Exception:
        spacing = None

    findings = parse_segmentation_output(output_dir, label_map=TOTAL_SEGMENTATOR_LABEL_MAP, spacing=spacing)
    annotated = extract_annotated_slices(output_dir, volume_path=volume_path, max_slices=6)

    regions_analyzed = set()
    for f in findings:
        label = f.get("label", "").lower()
        if "vertebra" in label:
            regions_analyzed.add("spine")
        elif any(b in label for b in ["femur", "tibia", "fibula", "patella"]):
            regions_analyzed.add("legs")
        elif any(b in label for b in ["hip", "pelvis", "sacrum"]):
            regions_analyzed.add("pelvis")
        elif any(b in label for b in ["rib", "sternum"]):
            regions_analyzed.add("thorax")
        elif any(b in label for b in ["humerus", "clavicula", "scapula"]):
            regions_analyzed.add("upper_extremity")
        elif any(b in label for b in ["tarsal", "metatarsal", "phalanges_feet"]):
            regions_analyzed.add("foot")
        elif any(b in label for b in ["carpal", "metacarpal", "phalanges_hand"]):
            regions_analyzed.add("hand")

    summary = {
        "total_structures": len(findings),
        "regions_analyzed": sorted(regions_analyzed),
        "task": "total",
        "model": "TotalSegmentator",
    }

    shutil.rmtree(output_dir, ignore_errors=True)

    return {
        "findings": findings,
        "summary": summary,
        "annotated_slices_base64": annotated,
    }


__all__ = ["ct_analyze_full_body_impl"]
