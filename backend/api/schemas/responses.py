from __future__ import annotations

from pydantic import BaseModel


class AgentResponse(BaseModel):
    chat_id: str | None = None
    message_id: str | None = None
    session_id: str
    final_response: str
    modality: str | None = None
    body_region: str | None = None
    body_part: str | None = None
    diagnosis: dict | None = None
    triage: dict | None = None
    hospitals: list[dict] | None = None
    report_url: str | None = None
    annotated_image_base64: str | None = None
    annotated_slices_base64: list[str] | None = None
    agent_trace: list[dict] | None = None


class ChatSessionSummary(BaseModel):
    chat_id: str
    title: str
    owner_role: str
    patient_id: str
    doctor_id: str | None = None
    last_message_at: str
    created_at: str


class ChatMessageRecord(BaseModel):
    message_id: str
    chat_id: str
    sender_role: str
    content: str
    attachment_data_url: str | None = None
    annotated_image_base64: str | None = None
    agent_trace: list[dict] | None = None
    created_at: str


class ChatSessionCreateResponse(BaseModel):
    chat_id: str
    title: str


class KnowledgeDocumentIngestResponse(BaseModel):
    document_id: str
    chunk_count: int


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
