from __future__ import annotations

import asyncio
import inspect
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger

from core.config import settings


def _get_totalsegmentator_task(task: str) -> str:
    return task


def _build_totalsegmentator_kwargs(
    totalsegmentator_fn: Any,
    nifti_path: str,
    output_dir: str,
    task: str,
    device: str,
    fast: bool,
    roi_subset: list[str] | None,
) -> dict[str, Any]:
    try:
        params = inspect.signature(totalsegmentator_fn).parameters
    except (TypeError, ValueError):
        params = {}

    kwargs: dict[str, Any] = {}

    if "input_path" in params:
        kwargs["input_path"] = nifti_path
    elif "input" in params:
        kwargs["input"] = nifti_path
    else:
        kwargs["input_path"] = nifti_path

    if "output_path" in params:
        kwargs["output_path"] = output_dir
    elif "output" in params:
        kwargs["output"] = output_dir
    else:
        kwargs["output_path"] = output_dir

    optional_args = {
        "task": task,
        "device": device,
        "fast": fast,
        "roi_subset": roi_subset,
    }

    for key, value in optional_args.items():
        if value is None:
            continue
        if not params or key in params:
            kwargs[key] = value

    return kwargs


def _predict_ct_sync(
    nifti_path: str,
    task: str,
    device: str = "cpu",
    fast: bool = True,
    roi_subset: list[str] | None = None,
) -> dict[str, Any]:
    output_dir = tempfile.mkdtemp(prefix="orthoassist_ct_")
    worker_cmd = [
        sys.executable,
        "-m",
        "tools.ct.totalsegmentator_worker",
        "--input",
        nifti_path,
        "--output",
        output_dir,
        "--task",
        task,
        "--device",
        device,
    ]
    if fast:
        worker_cmd.append("--fast")
    if roi_subset:
        worker_cmd.append("--roi-subset")
        worker_cmd.extend(roi_subset)

    try:
        logger.info(
            "Running TotalSegmentator in isolated worker: task={} device={} fast={} roi_subset={}",
            task,
            device,
            fast,
            roi_subset or [],
        )

        completed = __import__("subprocess").run(
            worker_cmd,
            capture_output=True,
            text=True,
            timeout=1800,
            cwd=str(Path(__file__).resolve().parents[2]),
            env={**os.environ},
        )

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode != 0:
            error_message = f"TotalSegmentator worker exited with code {completed.returncode}"
            if stdout:
                try:
                    payload = json.loads(stdout.splitlines()[-1])
                    if isinstance(payload, dict) and payload.get("error"):
                        error_message = str(payload["error"])
                except json.JSONDecodeError:
                    error_message = f"{error_message}. {stdout[-500:]}"
            elif stderr:
                error_message = f"{error_message}. {stderr[-500:]}"
            logger.error("TotalSegmentator inference failed: {}", error_message)
            shutil.rmtree(output_dir, ignore_errors=True)
            return {"error": error_message, "findings": [], "summary": {}}

        return {"output_dir": output_dir}
    except Exception as exc:
        logger.error("TotalSegmentator inference failed: {}", exc)
        shutil.rmtree(output_dir, ignore_errors=True)
        return {"error": str(exc), "findings": [], "summary": {}}


async def run_totalsegmentator(
    nifti_path: str,
    task: str = "total",
    device: str = "cpu",
    fast: bool = True,
    roi_subset: list[str] | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _predict_ct_sync,
        nifti_path,
        task,
        device,
        fast,
        roi_subset,
    )


async def run_verse_nnunet(
    nifti_path: str,
    output_dir: str | None = None,
) -> dict[str, Any]:
    try:
        import subprocess
        import tempfile
    except ImportError:
        return {"error": "Required imports not available"}

    out = output_dir or tempfile.mkdtemp(prefix="orthoassist_verse_")

    try:
        from core.config import settings as cfg
        model_dir = cfg.verse_model_path

        cmd = [
            "nnUNetv2_predict",
            "-i", nifti_path,
            "-o", out,
            "-d", "001",
            "-c", "3d_lowres",
            "-f", "0", "1",
        ]

        env_setup = f"nnUNet_results={model_dir}" if model_dir else ""
        result = await asyncio.to_thread(
            lambda: subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                env={**__import__("os").environ, **({"nnUNet_results": model_dir} if model_dir else {})},
            )
        )

        if result.returncode != 0:
            logger.error("VerSe nnUNet prediction failed: {}", result.stderr)
            return {"error": result.stderr, "findings": [], "output_dir": out}

        return {"output_dir": out}
    except Exception as exc:
        logger.error("VerSe inference error: {}", exc)
        return {"error": str(exc), "findings": [], "output_dir": out}
