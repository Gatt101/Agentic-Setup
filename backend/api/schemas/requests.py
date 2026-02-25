from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    image_data: str = Field(..., description="Base64-encoded X-ray image")
    symptoms: str | None = None
    user_message: str | None = None
    patient_id: str | None = None
    location: str | None = None
    session_id: str | None = None
    filename: str = "xray.png"


class ChatRequest(BaseModel):
    actor_id: str
    actor_role: str = "patient"
    actor_name: str | None = None  # display name from Clerk, used in PDF doctor field
    message: str
    session_id: str | None = None
    attachment: str | None = None
    patient_id: str | None = None
    location: str | None = None


class ChatSessionCreateRequest(BaseModel):
    actor_id: str
    actor_role: str = "patient"
    patient_id: str | None = None
    title: str | None = None


class DoctorPatientAssignRequest(BaseModel):
    doctor_id: str
    patient_id: str


class KnowledgeDocumentIngestRequest(BaseModel):
    title: str
    content: str
    source: str = "manual"
    patient_id: str | None = None


class ReportSaveRequest(BaseModel):
    report_data: dict
    patient_id: str
    report_type: str = "manual"


class ReportRetrieveRequest(BaseModel):
    report_id: str
