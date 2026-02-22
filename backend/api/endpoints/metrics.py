from __future__ import annotations

from fastapi import APIRouter

from api.schemas.responses import MetricsResponse
from services.session import session_store
from services.storage import storage_service


router = APIRouter(tags=["system"])


@router.get("/metrics", response_model=MetricsResponse)
async def metrics() -> MetricsResponse:
    session_metrics = session_store.metrics()
    report_count = len(list(storage_service.reports_dir.glob("*.json"))) if storage_service.reports_dir.exists() else 0
    return MetricsResponse(
        active_sessions=session_metrics["active_sessions"],
        stored_reports=report_count,
    )
