from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from core.config import settings


class MongoService:
    def __init__(self) -> None:
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None

    @property
    def enabled(self) -> bool:
        return bool(settings.mongodb_uri.strip())

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            raise RuntimeError("MongoDB is not initialized. Set MONGODB_URI and restart the server.")
        return self._db

    async def initialize(self) -> None:
        if not self.enabled:
            return
        if self._client is not None:
            return

        self._client = AsyncIOMotorClient(settings.mongodb_uri)
        self._db = self._client[settings.mongodb_db_name]
        await self._db.command("ping")
        await self._ensure_indexes()

    async def _ensure_indexes(self) -> None:
        db = self.db
        await db.chat_sessions.create_index([("chat_id", 1)], unique=True)
        await db.chat_sessions.create_index([("owner_user_id", 1), ("last_message_at", -1)])
        await db.chat_sessions.create_index([("patient_id", 1), ("last_message_at", -1)])
        await db.chat_sessions.create_index([("doctor_id", 1), ("last_message_at", -1)])

        await db.chat_messages.create_index([("message_id", 1)], unique=True)
        await db.chat_messages.create_index([("chat_id", 1), ("created_at", 1)])

        await db.chat_traces.create_index([("chat_id", 1)])
        await db.chat_traces.create_index([("chat_id", 1), ("created_at", -1)])

        await db.doctor_patient_assignments.create_index(
            [("doctor_id", 1), ("patient_id", 1)],
            unique=True,
        )

        await db.kb_documents.create_index([("document_id", 1)], unique=True)
        await db.kb_documents.create_index([("patient_id", 1), ("created_at", -1)])

        await db.kb_chunks.create_index([("document_id", 1)])
        await db.kb_chunks.create_index([("patient_id", 1), ("created_at", -1)])

        # patients
        await db.patients.create_index([("patient_id", 1)], unique=True)
        await db.patients.create_index([("doctor_user_id", 1), ("updated_at", -1)])
        await db.patients.create_index([("patient_user_id", 1), ("updated_at", -1)])

        # reports
        await db.reports.create_index([("report_id", 1)], unique=True)
        await db.reports.create_index([("doctor_user_id", 1), ("created_at", -1)])
        await db.reports.create_index([("patient_id", 1), ("created_at", -1)])

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._db = None


mongo_service = MongoService()
