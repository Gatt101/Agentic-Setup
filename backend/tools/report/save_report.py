from __future__ import annotations

from langchain_core.tools import tool

from services.storage import storage_service


async def save_report_to_storage_impl(report_data: dict, patient_id: str, report_type: str) -> dict:
    """Persist structured report JSON in storage."""
    return await storage_service.save_report(
        report_data=report_data,
        patient_id=patient_id,
        report_type=report_type,
    )


@tool("report_save_report_to_storage")
async def save_report_to_storage(report_data: dict, patient_id: str, report_type: str) -> dict:
    """Save report metadata payload and return id/path."""
    return await save_report_to_storage_impl(report_data, patient_id, report_type)


__all__ = ["save_report_to_storage", "save_report_to_storage_impl"]
