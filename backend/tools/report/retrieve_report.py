from __future__ import annotations

from langchain_core.tools import tool

from services.storage import storage_service


async def retrieve_report_impl(report_id: str) -> dict:
    """Fetch report metadata and stored PDF URL."""
    payload = await storage_service.retrieve_report(report_id)
    return {
        "report_data": payload.get("report_data", {}),
        "pdf_url": payload.get("pdf_url"),
        "created_at": payload.get("created_at"),
    }


@tool("report_retrieve_report")
async def retrieve_report(report_id: str) -> dict:
    """Retrieve a report by report id."""
    return await retrieve_report_impl(report_id)


__all__ = ["retrieve_report", "retrieve_report_impl"]
