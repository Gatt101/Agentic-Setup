from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiofiles

from core.config import settings
from core.exceptions import StorageError


def _strip_data_url_prefix(value: str) -> str:
    if "," in value and value.strip().startswith("data:"):
        return value.split(",", 1)[1]
    return value


class StorageService:
    def __init__(self) -> None:
        self.root = settings.resolved_storage_path
        self.raw_dir = self.root / "raw"
        self.annotated_dir = self.root / "annotated"
        self.reports_dir = self.root / "reports"

    async def initialize(self) -> None:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.annotated_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def _make_public_url(self, path: Path) -> str:
        return f"/{path.relative_to(self.root).as_posix()}"

    async def save_bytes(self, data: bytes, filename: str, subdir: str = "raw") -> dict[str, str]:
        target_dir = self.root / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / filename

        async with aiofiles.open(file_path, "wb") as handle:
            await handle.write(data)

        return {
            "path": str(file_path),
            "public_id": file_path.stem,
            "public_url": self._make_public_url(file_path),
        }

    async def save_base64_image(
        self,
        image_base64: str,
        filename: str,
        patient_id: str,
        subdir: str = "raw",
    ) -> dict[str, str]:
        try:
            payload = _strip_data_url_prefix(image_base64)
            image_bytes = base64.b64decode(payload)
        except Exception as exc:  # pragma: no cover - defensive guard
            raise StorageError("Invalid base64 image payload") from exc

        suffix = Path(filename).suffix or ".png"
        safe_name = f"{patient_id}_{uuid4().hex}{suffix}"
        return await self.save_bytes(image_bytes, safe_name, subdir=subdir)

    async def save_report(
        self,
        report_data: dict[str, Any],
        patient_id: str,
        report_type: str,
        pdf_url: str | None = None,
        report_id: str | None = None,
    ) -> dict[str, str]:
        rid = report_id or uuid4().hex
        timestamp = datetime.now(UTC).isoformat()
        record = {
            "report_id": rid,
            "patient_id": patient_id,
            "report_type": report_type,
            "report_data": report_data,
            "pdf_url": pdf_url,
            "created_at": timestamp,
        }

        report_path = self.reports_dir / f"{rid}.json"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(report_path, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps(record, ensure_ascii=True, indent=2))

        return {
            "report_id": rid,
            "saved_path": str(report_path),
            "timestamp": timestamp,
        }

    async def retrieve_report(self, report_id: str) -> dict[str, Any]:
        report_path = self.reports_dir / f"{report_id}.json"
        if not report_path.exists():
            raise StorageError(f"Report '{report_id}' not found")

        async with aiofiles.open(report_path, "r", encoding="utf-8") as handle:
            payload = await handle.read()

        return json.loads(payload)

    async def get_patient_history(self, patient_id: str) -> dict[str, Any]:
        studies: list[dict[str, Any]] = []
        if not self.reports_dir.exists():
            return {"past_studies": studies, "study_count": 0, "last_visit": ""}

        for file_path in self.reports_dir.glob("*.json"):
            async with aiofiles.open(file_path, "r", encoding="utf-8") as handle:
                content = await handle.read()
            item = json.loads(content)
            if item.get("patient_id") == patient_id:
                studies.append(item)

        studies.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        last_visit = studies[0].get("created_at", "") if studies else ""
        return {
            "past_studies": studies,
            "study_count": len(studies),
            "last_visit": last_visit,
        }


storage_service = StorageService()
