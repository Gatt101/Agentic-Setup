from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    image_data: str | None = Field(default=None, description="Base64-encoded X-ray image")
    dicom_data: str | None = Field(default=None, description="Base64-encoded DICOM file")
    modality: str | None = None
    body_region: str | None = None
    symptoms: str | None = None
    user_message: str | None = None
    patient_id: str | None = None
    location: str | None = None
    session_id: str | None = None
    filename: str = "xray.png"


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    session_id: str | None = None
    attachment: str | None = None
    deidentified_confirmed: bool = False
    patient_id: str | None = None
    location: str | None = None


class ChatSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str | None = None
    title: str | None = None


class KnowledgeDocumentIngestRequest(BaseModel):
    title: str
    content: str
    source: str = "manual"
    patient_id: str | None = None


class ReportRetrieveRequest(BaseModel):
    report_id: str
