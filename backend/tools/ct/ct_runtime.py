from __future__ import annotations

import asyncio
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
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
        logger.info("TotalSegmentator worker command: {}", worker_cmd)

        process = subprocess.Popen(
            worker_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(Path(__file__).resolve().parents[2]),
            env={**os.environ},
        )
        logger.info("TotalSegmentator worker started with pid={}", process.pid)

        deadline = time.monotonic() + 1800
        last_progress_log = time.monotonic()
        output_lines: list[str] = []

        while True:
            now = time.monotonic()
            if now >= deadline:
                process.kill()
                raise TimeoutError("TotalSegmentator worker timed out after 1800 seconds")

            line = process.stdout.readline() if process.stdout else ""
            if line:
                text_line = line.rstrip()
                output_lines.append(text_line)
                logger.info("TotalSegmentator worker | {}", text_line)
                last_progress_log = now
                continue

            return_code = process.poll()
            if return_code is not None:
                break

            if now - last_progress_log >= 30:
                logger.info(
                    "TotalSegmentator worker pid={} still running for {:.0f}s",
                    process.pid,
                    now - (deadline - 1800),
                )
                last_progress_log = now
            time.sleep(1)

        if process.stdout:
            remaining = process.stdout.read()
            if remaining:
                for line in remaining.splitlines():
                    text_line = line.rstrip()
                    output_lines.append(text_line)
                    logger.info("TotalSegmentator worker | {}", text_line)

        if process.returncode != 0:
            error_message = f"TotalSegmentator worker exited with code {process.returncode}"
            if output_lines:
                try:
                    payload = json.loads(output_lines[-1])
                    if isinstance(payload, dict) and payload.get("error"):
                        error_message = str(payload["error"])
                except json.JSONDecodeError:
                    error_message = f"{error_message}. {output_lines[-1][-500:]}"
            logger.error("TotalSegmentator inference failed: {}", error_message)
            shutil.rmtree(output_dir, ignore_errors=True)
            return {"error": error_message, "findings": [], "summary": {}}

        logger.info(
            "TotalSegmentator worker completed successfully: pid={} output_dir={}",
            process.pid,
            output_dir,
        )

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
