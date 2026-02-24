from __future__ import annotations

from fastapi import APIRouter

from api.schemas.responses import MetricsResponse
from services.mongo import mongo_service
from services.storage import storage_service


router = APIRouter(tags=["system"])


@router.get("/metrics", response_model=MetricsResponse)
async def metrics() -> MetricsResponse:
    active_sessions = 0
    if mongo_service.enabled:
        await mongo_service.initialize()
        active_sessions = await mongo_service.db.chat_traces.count_documents({"status": "running"})
    report_count = len(list(storage_service.reports_dir.glob("*.json"))) if storage_service.reports_dir.exists() else 0
    return MetricsResponse(
        active_sessions=active_sessions,
        stored_reports=report_count,
    )
