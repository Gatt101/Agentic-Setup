from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from core.config import settings


@dataclass
class SessionRecord:
    values: dict[str, Any]
    expires_at: datetime


class InMemorySessionStore:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._records: dict[str, SessionRecord] = {}

    def _expiry(self) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=self.ttl_seconds)

    def _cleanup(self) -> None:
        now = datetime.now(UTC)
        expired = [key for key, record in self._records.items() if record.expires_at < now]
        for key in expired:
            self._records.pop(key, None)

    def set(self, session_id: str, values: dict[str, Any]) -> None:
        self._cleanup()
        self._records[session_id] = SessionRecord(values=values, expires_at=self._expiry())

    def init_run(self, session_id: str) -> None:
        self._cleanup()
        current = self.get(session_id) or {}
        current.update(
            {
                "status": "running",
                "trace": [],
            }
        )
        self._records[session_id] = SessionRecord(values=current, expires_at=self._expiry())

    def append_trace(self, session_id: str, event: dict[str, Any]) -> None:
        self._cleanup()
        current = self.get(session_id) or {"status": "running", "trace": []}
        trace = current.get("trace")
        if not isinstance(trace, list):
            trace = []
        trace.append(event)
        current["trace"] = trace
        self._records[session_id] = SessionRecord(values=current, expires_at=self._expiry())

    def mark_complete(self, session_id: str, values: dict[str, Any]) -> None:
        self._cleanup()
        current = self.get(session_id) or {}
        current.update(values)
        current["status"] = "completed"
        self._records[session_id] = SessionRecord(values=current, expires_at=self._expiry())

    def get_trace(self, session_id: str) -> dict[str, Any]:
        record = self.get(session_id) or {}
        trace = record.get("trace")
        return {
            "status": record.get("status", "idle"),
            "trace": trace if isinstance(trace, list) else [],
        }

    def get(self, session_id: str) -> dict[str, Any] | None:
        self._cleanup()
        record = self._records.get(session_id)
        if not record:
            return None
        return record.values

    def metrics(self) -> dict[str, int]:
        self._cleanup()
        return {"active_sessions": len(self._records)}


session_store = InMemorySessionStore(ttl_seconds=settings.session_ttl_seconds)
