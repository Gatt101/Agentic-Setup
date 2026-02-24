from __future__ import annotations

from fastapi import APIRouter, Query

from api.schemas.requests import KnowledgeDocumentIngestRequest
from api.schemas.responses import KnowledgeDocumentIngestResponse
from services.rag_store import rag_store


router = APIRouter(tags=["knowledge"])


@router.post("/knowledge/documents", response_model=KnowledgeDocumentIngestResponse)
async def ingest_knowledge_document(request: KnowledgeDocumentIngestRequest) -> KnowledgeDocumentIngestResponse:
    payload = await rag_store.ingest_document(
        title=request.title,
        content=request.content,
        source=request.source,
        patient_id=request.patient_id,
    )
    return KnowledgeDocumentIngestResponse(**payload)


@router.get("/knowledge/search")
async def search_knowledge(
    query: str = Query(..., min_length=3),
    patient_id: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    hits = await rag_store.retrieve(query=query, patient_id=patient_id, limit=limit)
    return {"results": hits}
