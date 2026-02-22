from __future__ import annotations

from fastapi import APIRouter

from api.schemas.responses import HealthResponse


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="orthoassist-backend", version="0.1.0")
