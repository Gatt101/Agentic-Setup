from __future__ import annotations

import shutil
from langchain_core.tools import tool
from loguru import logger

from tools.mri.mri_runtime import run_kneeseg


@tool("mri_analyze_knee")
async def mri_analyze_knee_impl(volume_path: str) -> dict:
    """Analyze knee MRI for bone and cartilage segmentation using SKI10 model.

    Segments femur, tibia, patella, femoral cartilage, tibial cartilage, and patellar cartilage.
    """
    logger.info("Starting knee MRI analysis: {}", volume_path)

    result = await run_kneeseg(volume_path)

    if "error" in result and not result.get("findings"):
        return {"findings": [], "summary": {"error": result["error"]}, "annotated_slices_base64": []}

    findings = result.get("findings", [])
    annotated = result.get("annotated_slices_base64", [])

    cartilage_structures = [f for f in findings if "cartilage" in f.get("label", "")]
    cartilage_total = sum(f.get("volume_mm3", 0) for f in cartilage_structures)

    bone_structures = [f for f in findings if "cartilage" not in f.get("label", "")]

    integrity = "normal"
    if len(cartilage_structures) > 0:
        volumes = [f.get("volume_mm3", 0) for f in cartilage_structures]
        if volumes and min(volumes) < max(volumes) * 0.3:
            integrity = "reduced"

    summary = {
        "total_structures": len(findings),
        "bone_structures": len(bone_structures),
        "cartilage_structures": len(cartilage_structures),
        "cartilage_total_volume_mm3": round(cartilage_total, 1),
        "cartilage_integrity": integrity,
        "task": "knee_mri",
        "model": "SKI10 (kneeseg)",
    }

    output_dir = result.get("output_dir")
    if output_dir:
        shutil.rmtree(output_dir, ignore_errors=True)

    return {
        "findings": findings,
        "summary": summary,
        "annotated_slices_base64": annotated,
    }


__all__ = ["mri_analyze_knee_impl"]
