from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import SimpleITK as sitk
from langchain_core.tools import tool
from loguru import logger

from tools.ct.ct_runtime import run_verse_nnunet
from tools.ct.ct_utils import extract_annotated_slices, parse_segmentation_output


VERSE_LABEL_MAP = {
    1: "vertebra_C1",
    2: "vertebra_C2",
    3: "vertebra_C3",
    4: "vertebra_C4",
    5: "vertebra_C5",
    6: "vertebra_C6",
    7: "vertebra_C7",
    8: "vertebra_T1",
    9: "vertebra_T2",
    10: "vertebra_T3",
    11: "vertebra_T4",
    12: "vertebra_T5",
    13: "vertebra_T6",
    14: "vertebra_T7",
    15: "vertebra_T8",
    16: "vertebra_T9",
    17: "vertebra_T10",
    18: "vertebra_T11",
    19: "vertebra_T12",
    20: "vertebra_L1",
    21: "vertebra_L2",
    22: "vertebra_L3",
    23: "vertebra_L4",
    24: "vertebra_L5",
    25: "vertebra_L6",
    26: "vertebra_S1",
}


@tool("ct_analyze_spine")
async def ct_analyze_spine_impl(volume_path: str) -> dict:
    """Analyze spine CT using dedicated VerSe nnUNet vertebrae segmentation model.

    Segments individual vertebrae C1-S1 with higher accuracy than TotalSegmentator.
    """
    logger.info("Starting VerSe spine CT analysis: {}", volume_path)

    from core.config import settings as cfg
    if not cfg.verse_model_path:
        logger.warning("VerSe model path not configured, falling back to TotalSegmentator")
        from tools.ct.ct_runtime import run_totalsegmentator
        from tools.ct.ct_utils import TOTAL_SEGMENTATOR_LABEL_MAP

        result = await run_totalsegmentator(volume_path, task="vertebrae_body", device="cpu", fast=True)
        output_dir = result.get("output_dir", "")
        if "error" in result:
            return {"findings": [], "summary": {"error": result["error"]}, "annotated_slices_base64": []}

        try:
            spacing = sitk.ReadImage(volume_path).GetSpacing()
        except Exception:
            spacing = None

        findings = parse_segmentation_output(output_dir, label_map=TOTAL_SEGMENTATOR_LABEL_MAP, spacing=spacing)
        annotated = extract_annotated_slices(output_dir, volume_path=volume_path, max_slices=8)

        vertebrae = [f for f in findings if "vertebra" in f.get("label", "")]
        affected = [f.get("location", {}).get("vertebra", "") for f in vertebrae if f.get("location", {}).get("vertebra")]

        summary = {
            "total_vertebrae": len(vertebrae),
            "affected_vertebrae": affected,
            "regions_analyzed": ["spine"],
            "task": "vertebrae_body",
            "model": "TotalSegmentator (fallback - VerSe not configured)",
        }

        shutil.rmtree(output_dir, ignore_errors=True)
        return {"findings": findings, "summary": summary, "annotated_slices_base64": annotated}

    result = await run_verse_nnunet(volume_path)
    output_dir = result.get("output_dir", "")

    if "error" in result:
        return {"findings": [], "summary": {"error": result["error"]}, "annotated_slices_base64": []}

    try:
        spacing = sitk.ReadImage(volume_path).GetSpacing()
    except Exception:
        spacing = None

    findings = parse_segmentation_output(output_dir, label_map=VERSE_LABEL_MAP, spacing=spacing)
    annotated = extract_annotated_slices(output_dir, volume_path=volume_path, max_slices=8)

    vertebrae = [f for f in findings if "vertebra" in f.get("label", "")]
    affected = [f.get("location", {}).get("vertebra", "") for f in vertebrae if f.get("location", {}).get("vertebra")]

    summary = {
        "total_vertebrae": len(vertebrae),
        "affected_vertebrae": affected,
        "regions_analyzed": ["spine"],
        "task": "verse_spine",
        "model": "VerSe nnUNet",
    }

    shutil.rmtree(output_dir, ignore_errors=True)

    return {
        "findings": findings,
        "summary": summary,
        "annotated_slices_base64": annotated,
    }


__all__ = ["ct_analyze_spine_impl"]
