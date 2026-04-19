from __future__ import annotations

import argparse
import json
import shutil
import sys

from loguru import logger

from tools.ct.ct_runtime import _build_totalsegmentator_kwargs


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TotalSegmentator in an isolated worker process")
    parser.add_argument("--input", dest="input_path", required=True)
    parser.add_argument("--output", dest="output_path", required=True)
    parser.add_argument("--task", default="total")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--roi-subset", nargs="*")
    args = parser.parse_args()

    try:
        from totalsegmentator.python_api import totalsegmentator
    except ImportError:
        print(json.dumps({"error": "TotalSegmentator not installed"}), flush=True)
        return 2

    try:
        kwargs = _build_totalsegmentator_kwargs(
            totalsegmentator,
            nifti_path=args.input_path,
            output_dir=args.output_path,
            task=args.task,
            device=args.device,
            fast=args.fast,
            roi_subset=args.roi_subset,
        )
        logger.info("Worker running TotalSegmentator with args: {}", sorted(kwargs.keys()))
        totalsegmentator(**kwargs)
    except Exception as exc:
        shutil.rmtree(args.output_path, ignore_errors=True)
        print(json.dumps({"error": str(exc)}), flush=True)
        return 1

    print(json.dumps({"output_dir": args.output_path}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
