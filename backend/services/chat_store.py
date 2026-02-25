from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from services.mongo import mongo_service


def _now() -> datetime:
    return datetime.now(UTC)


class ChatStore:
    async def ensure_enabled(self) -> None:
        if not mongo_service.enabled:
            raise RuntimeError("MongoDB is not configured. Set MONGODB_URI in backend/.env.")
        await mongo_service.initialize()

    async def assign_patient_to_doctor(self, doctor_id: str, patient_id: str) -> None:
        await self.ensure_enabled()
        await mongo_service.db.doctor_patient_assignments.update_one(
            {"doctor_id": doctor_id, "patient_id": patient_id},
            {
                "$set": {
                    "doctor_id": doctor_id,
                    "patient_id": patient_id,
                    "updated_at": _now(),
                },
                "$setOnInsert": {"created_at": _now()},
            },
            upsert=True,
        )

    async def is_patient_assigned(self, doctor_id: str, patient_id: str) -> bool:
        await self.ensure_enabled()
        row = await mongo_service.db.doctor_patient_assignments.find_one(
            {"doctor_id": doctor_id, "patient_id": patient_id},
            projection={"_id": 1},
        )
        return row is not None

    async def create_session(
        self,
        chat_id: str,
        actor_id: str,
        actor_role: str,
        patient_id: str,
        doctor_id: str | None,
        title: str,
    ) -> dict[str, Any]:
        await self.ensure_enabled()
        now = _now()
        document = {
            "chat_id": chat_id,
            "owner_user_id": actor_id,
            "owner_role": actor_role,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "title": title,
            "status": "active",
            "created_at": now,
            "last_message_at": now,
        }
        await mongo_service.db.chat_sessions.insert_one(document)
        return document

    async def get_session(self, chat_id: str) -> dict[str, Any] | None:
        await self.ensure_enabled()
        return await mongo_service.db.chat_sessions.find_one({"chat_id": chat_id}, {"_id": 0})

    async def list_sessions(self, actor_id: str, actor_role: str) -> list[dict[str, Any]]:
        await self.ensure_enabled()
        if actor_role == "doctor":
            query = {"doctor_id": actor_id}
        else:
            query = {"patient_id": actor_id}

        cursor = (
            mongo_service.db.chat_sessions.find(query, {"_id": 0})
            .sort("last_message_at", -1)
            .limit(100)
        )
        return [row async for row in cursor]

    async def append_message(
        self,
        chat_id: str,
        message_id: str,
        sender_role: str,
        content: str,
        attachment_data_url: str | None = None,
        annotated_image_base64: str | None = None,
        agent_trace: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        await self.ensure_enabled()
        now = _now()
        message = {
            "message_id": message_id,
            "chat_id": chat_id,
            "sender_role": sender_role,
            "content": content,
            "attachment_data_url": attachment_data_url,
            "annotated_image_base64": annotated_image_base64,
            "agent_trace": agent_trace or [],
            "created_at": now,
        }
        await mongo_service.db.chat_messages.insert_one(message)
        await mongo_service.db.chat_sessions.update_one(
            {"chat_id": chat_id},
            {"$set": {"last_message_at": now}},
        )
        return message

    async def get_messages(self, chat_id: str) -> list[dict[str, Any]]:
        await self.ensure_enabled()
        cursor = mongo_service.db.chat_messages.find({"chat_id": chat_id}, {"_id": 0}).sort("created_at", 1)
        return [row async for row in cursor]

    async def init_trace(self, chat_id: str) -> None:
        await self.ensure_enabled()
        await mongo_service.db.chat_traces.insert_one(
            {
                "chat_id": chat_id,
                "status": "running",
                "events": [],
                "created_at": _now(),
                "updated_at": _now(),
            }
        )

    async def append_trace_event(self, chat_id: str, event: dict[str, Any]) -> None:
        await self.ensure_enabled()
        await mongo_service.db.chat_traces.update_one(
            {"chat_id": chat_id},
            {
                "$set": {"updated_at": _now()},
                "$push": {"events": event},
            },
            upsert=True,
        )

    async def complete_trace(self, chat_id: str, final_events: list[dict[str, Any]]) -> None:
        await self.ensure_enabled()
        await mongo_service.db.chat_traces.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "status": "completed",
                    "events": final_events,
                    "updated_at": _now(),
                }
            },
            upsert=True,
        )

    async def get_trace(self, chat_id: str) -> dict[str, Any]:
        await self.ensure_enabled()
        row = await mongo_service.db.chat_traces.find_one(
            {"chat_id": chat_id},
            projection={"_id": 0, "status": 1, "events": 1},
            sort=[("updated_at", -1)],
        )
        if not row:
            return {"status": "idle", "trace": []}
        return {
            "status": row.get("status", "idle"),
            "trace": row.get("events", []),
        }

    # ── Clinical pipeline state ────────────────────────────────────────────────
    async def save_pipeline_state(self, chat_id: str, state: dict[str, Any]) -> None:
        """Persist diagnosis, triage, body_part, detections, patient_info per session."""
        await self.ensure_enabled()
        fields: dict[str, Any] = {"pipeline_state_updated_at": _now()}
        for key in ("diagnosis", "triage_result", "body_part", "detections", "patient_info"):
            if key in state and state[key] is not None:
                fields[f"pipeline_{key}"] = state[key]
        # pending_report_actor_role must always be written (None explicitly clears it)
        if "pending_report_actor_role" in state:
            fields["pipeline_pending_report_actor_role"] = state["pending_report_actor_role"]
        await mongo_service.db.chat_sessions.update_one(
            {"chat_id": chat_id},
            {"$set": fields},
        )

    async def get_pipeline_state(self, chat_id: str) -> dict[str, Any]:
        """Load persisted clinical state for a session."""
        await self.ensure_enabled()
        row = await mongo_service.db.chat_sessions.find_one(
            {"chat_id": chat_id},
            projection={
                "_id": 0,
                "pipeline_diagnosis": 1,
                "pipeline_triage_result": 1,
                "pipeline_body_part": 1,
                "pipeline_detections": 1,
                "pipeline_patient_info": 1,
                "pipeline_pending_report_actor_role": 1,
            },
        )
        if not row:
            return {}
        out: dict[str, Any] = {}
        for key in ("diagnosis", "triage_result", "body_part", "detections", "patient_info", "pending_report_actor_role"):
            val = row.get(f"pipeline_{key}")
            if val is not None:
                out[key] = val
        return out


chat_store = ChatStore()
