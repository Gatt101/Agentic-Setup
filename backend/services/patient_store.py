"""Patient and report persistence in MongoDB.

Patients are created when a doctor (or patient user) provides their details in
the intake greeting at the start of a chat session.  Reports are linked to that
patient record when a PDF is generated.
"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from services.mongo import mongo_service


def _human_readable_patient_id(raw_id: str) -> str:
    """Mirror the PDF patient-id normalization logic (PT-YYYY-XXXXXX)."""
    raw = str(raw_id or "").strip().upper()
    if re.fullmatch(r"PT-\d{4}-[A-F0-9]{6}", raw):
        return raw

    clean = re.sub(r"[^a-zA-Z0-9]", "", str(raw_id))
    hash_suffix = hashlib.md5(clean.encode()).hexdigest()[:6].upper()
    year = datetime.now(UTC).year
    return f"PT-{year}-{hash_suffix}"


def _now() -> datetime:
    return datetime.now(UTC)


def _make_patient_id(seed: str | None = None) -> str:
    """Use the same patient-id format logic used by PDF generation."""
    return _human_readable_patient_id(seed or uuid4().hex)


def _make_report_id() -> str:
    """e.g. REP-E5F6A7B8"""
    return f"REP-{uuid4().hex[:8].upper()}"


class PatientStore:
    # ── helpers ───────────────────────────────────────────────────────────────
    async def ensure_enabled(self) -> None:
        if not mongo_service.enabled:
            raise RuntimeError("MongoDB is not configured. Set MONGODB_URI in backend/.env.")
        await mongo_service.initialize()

    # ── patients ──────────────────────────────────────────────────────────────

    async def upsert_patient(
        self,
        name: str,
        age: int | None = None,
        gender: str | None = None,
        doctor_user_id: str | None = None,
        patient_user_id: str | None = None,
        chat_id: str | None = None,
        existing_patient_id: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a patient record.

        Lookup priority:
        1. existing_patient_id (passed from pipeline state after first upsert)
        2. doctor_user_id + name match (prevent duplicate records per doctor)
        3. Create new record
        """
        await self.ensure_enabled()
        now = _now()

        # 1 – update by known patient_id
        if existing_patient_id:
            existing = await mongo_service.db.patients.find_one(
                {"patient_id": existing_patient_id}, {"_id": 0}
            )
            if existing:
                update: dict[str, Any] = {"updated_at": now}
                if name:
                    update["name"] = name
                if age is not None:
                    update["age"] = age
                if gender:
                    update["gender"] = gender
                if doctor_user_id:
                    update["doctor_user_id"] = doctor_user_id
                if patient_user_id:
                    update["patient_user_id"] = patient_user_id
                if chat_id:
                    update["chat_id"] = chat_id
                await mongo_service.db.patients.update_one(
                    {"patient_id": existing_patient_id}, {"$set": update}
                )
                return {**existing, **update}

        # 2 – find by doctor + name (case-insensitive)
        if doctor_user_id and name:
            try:
                name_pattern = re.compile(f"^{re.escape(name.strip())}$", re.IGNORECASE)
                existing_by_name = await mongo_service.db.patients.find_one(
                    {"doctor_user_id": doctor_user_id, "name": name_pattern},
                    {"_id": 0},
                )
            except Exception:
                existing_by_name = None  # regex error

            if existing_by_name:
                update = {
                    "updated_at": now,
                    **({"age": age} if age is not None else {}),
                    **({"gender": gender} if gender else {}),
                    **({"chat_id": chat_id} if chat_id else {}),
                }
                await mongo_service.db.patients.update_one(
                    {"patient_id": existing_by_name["patient_id"]}, {"$set": update}
                )
                return {**existing_by_name, **update}

        # 3 – create new (retry on extremely unlikely ID collision)
        for _ in range(5):
            patient_id = _make_patient_id()
            doc: dict[str, Any] = {
                "patient_id": patient_id,
                "name": name or "",
                "age": age,
                "gender": gender or "",
                "doctor_user_id": doctor_user_id,
                "patient_user_id": patient_user_id,
                "chat_id": chat_id,
                "analyses": [],
                "created_at": now,
                "updated_at": now,
            }
            try:
                await mongo_service.db.patients.insert_one(doc)
                return {k: v for k, v in doc.items() if k != "_id"}
            except Exception as exc:
                # Retry only for duplicate-key collisions on patient_id.
                if "E11000" in str(exc) and "patient_id" in str(exc):
                    continue
                raise

        raise RuntimeError("Unable to allocate a unique patient_id after retries.")

    async def add_analysis(self, patient_id: str, analysis: dict[str, Any]) -> None:
        """Append an X-ray analysis record to the patient's analyses array."""
        await self.ensure_enabled()
        entry = {**analysis, "created_at": _now().isoformat()}
        await mongo_service.db.patients.update_one(
            {"patient_id": patient_id},
            {
                "$push": {"analyses": entry},
                "$set": {"updated_at": _now()},
            },
        )

    async def get_patient(self, patient_id: str) -> dict[str, Any] | None:
        await self.ensure_enabled()
        return await mongo_service.db.patients.find_one(
            {"patient_id": patient_id}, {"_id": 0}
        )

    async def list_by_doctor(self, doctor_user_id: str) -> list[dict[str, Any]]:
        await self.ensure_enabled()
        cursor = (
            mongo_service.db.patients.find(
                {"doctor_user_id": doctor_user_id}, {"_id": 0, "analyses": 0}
            )
            .sort("updated_at", -1)
            .limit(200)
        )
        return [row async for row in cursor]

    async def list_by_patient_user(self, patient_user_id: str) -> list[dict[str, Any]]:
        await self.ensure_enabled()
        cursor = (
            mongo_service.db.patients.find(
                {"patient_user_id": patient_user_id}, {"_id": 0, "analyses": 0}
            )
            .sort("updated_at", -1)
            .limit(200)
        )
        return [row async for row in cursor]

    # ── reports ───────────────────────────────────────────────────────────────

    async def save_report(
        self,
        patient_id: str,
        patient_name: str,
        pdf_url: str,
        title: str,
        severity: str,
        doctor_user_id: str | None = None,
        report_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist a generated PDF report to the reports collection."""
        await self.ensure_enabled()
        rid = report_id or _make_report_id()
        now = _now()
        doc: dict[str, Any] = {
            "report_id": rid,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "pdf_url": pdf_url,
            "title": title or "Orthopedic Analysis Report",
            "severity": (severity or "GREEN").upper(),
            "status": "finalized",
            "doctor_user_id": doctor_user_id,
            "created_at": now,
        }
        await mongo_service.db.reports.insert_one(doc)
        return {k: v for k, v in doc.items() if k != "_id"}

    async def list_reports_by_doctor(
        self, doctor_user_id: str
    ) -> list[dict[str, Any]]:
        await self.ensure_enabled()
        cursor = (
            mongo_service.db.reports.find(
                {"doctor_user_id": doctor_user_id}, {"_id": 0}
            )
            .sort("created_at", -1)
            .limit(200)
        )
        return [row async for row in cursor]

    async def list_reports_by_patient_id(
        self, patient_id: str
    ) -> list[dict[str, Any]]:
        await self.ensure_enabled()
        cursor = (
            mongo_service.db.reports.find(
                {"patient_id": patient_id}, {"_id": 0}
            )
            .sort("created_at", -1)
            .limit(200)
        )
        return [row async for row in cursor]


patient_store = PatientStore()
