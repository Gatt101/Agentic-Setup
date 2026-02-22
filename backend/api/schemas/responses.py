from __future__ import annotations

from pydantic import BaseModel


class AgentResponse(BaseModel):
    session_id: str
    final_response: str
    body_part: str | None = None
    diagnosis: dict | None = None
    triage: dict | None = None
    hospitals: list[dict] | None = None
    report_url: str | None = None


class ReportSaveResponse(BaseModel):
    report_id: str
    saved_path: str
    timestamp: str


class ReportRetrieveResponse(BaseModel):
    report_data: dict
    pdf_url: str | None = None
    created_at: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class MetricsResponse(BaseModel):
    active_sessions: int
    stored_reports: int
