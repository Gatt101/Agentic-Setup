from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from services.mongo import mongo_service


def _now() -> datetime:
    return datetime.now(UTC)


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = max(0, end - overlap)
    return chunks


class RagStore:
    async def ensure_enabled(self) -> None:
        if not mongo_service.enabled:
            raise RuntimeError("MongoDB is not configured. Set MONGODB_URI in backend/.env.")
        await mongo_service.initialize()

    async def ingest_document(
        self,
        title: str,
        content: str,
        source: str,
        patient_id: str | None = None,
    ) -> dict[str, Any]:
        await self.ensure_enabled()
        document_id = str(uuid4())
        now = _now()
        chunks = _chunk_text(content)

        await mongo_service.db.kb_documents.insert_one(
            {
                "document_id": document_id,
                "title": title,
                "source": source,
                "patient_id": patient_id,
                "created_at": now,
            }
        )

        if chunks:
            await mongo_service.db.kb_chunks.insert_many(
                [
                    {
                        "chunk_id": str(uuid4()),
                        "document_id": document_id,
                        "title": title,
                        "source": source,
                        "patient_id": patient_id,
                        "text": chunk,
                        "created_at": now,
                    }
                    for chunk in chunks
                ]
            )

        return {
            "document_id": document_id,
            "chunk_count": len(chunks),
        }

    async def retrieve(self, query: str, patient_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        await self.ensure_enabled()
        tokens = [token for token in re.findall(r"[a-zA-Z0-9]{3,}", query.lower()) if token]
        if not tokens:
            return []

        filters: list[dict[str, Any]] = [{"patient_id": None}]
        if patient_id:
            filters.append({"patient_id": patient_id})

        pattern = "|".join(re.escape(token) for token in tokens)
        cursor = mongo_service.db.kb_chunks.find(
            {
                "$and": [
                    {"$or": filters},
                    {"text": {"$regex": pattern, "$options": "i"}},
                ]
            },
            projection={"_id": 0, "title": 1, "source": 1, "text": 1, "patient_id": 1},
        ).limit(100)
        candidates = [item async for item in cursor]

        def _score(item: dict[str, Any]) -> int:
            text = str(item.get("text", "")).lower()
            return sum(1 for token in tokens if token in text)

        ranked = sorted(candidates, key=_score, reverse=True)
        return ranked[: max(1, limit)]


rag_store = RagStore()
