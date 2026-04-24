from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from loguru import logger

from services.agent_learning import adaptive_supervisor


router = APIRouter(tags=["feedback"])


@router.get("/feedback/learning/summary")
async def get_learning_summary() -> Dict[str, Any]:
    """
    Get summary of agent learning progress and patterns.

    Provides insights into what the agent has learned from user feedback,
    including successful patterns, failure patterns, and confidence levels.
    """
    try:
        summary = adaptive_supervisor.get_learning_summary()
        return summary
    except Exception as e:
        logger.error("Failed to get learning summary: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get learning summary: {str(e)}")
