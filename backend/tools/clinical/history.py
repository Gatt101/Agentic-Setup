from __future__ import annotations

from langchain_core.tools import tool

from services.storage import storage_service


async def get_patient_history_impl(patient_id: str) -> dict:
    """Fetch previously saved report history for a patient."""
    return await storage_service.get_patient_history(patient_id)


@tool("clinical_get_patient_history")
async def get_patient_history(patient_id: str) -> dict:
    """Return historical studies and metadata for a patient id."""
    return await get_patient_history_impl(patient_id)


__all__ = ["get_patient_history", "get_patient_history_impl"]
