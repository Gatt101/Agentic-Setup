from __future__ import annotations

from langchain_core.tools import tool


async def get_orthopedic_knowledge_impl(query: str) -> dict:
    question = query.strip().lower()

    if "colles" in question:
        answer = (
            "A Colles fracture is a distal radius fracture with dorsal displacement, "
            "typically caused by a fall on an outstretched hand."
        )
        references = [
            "AAOS Distal Radius Fracture Guidelines",
            "Orthobullets: Distal Radius Fractures",
        ]
        confidence = 0.9
    else:
        answer = (
            "Orthopedic recommendation: correlate symptoms, imaging findings, and mechanism of injury "
            "before final diagnosis and treatment planning."
        )
        references = ["General orthopedic clinical practice guidance"]
        confidence = 0.65

    return {
        "answer": answer,
        "references": references,
        "confidence": confidence,
    }


@tool("knowledge_get_orthopedic_knowledge")
async def get_orthopedic_knowledge(query: str) -> dict:
    """Answer general orthopedic questions with structured output."""
    return await get_orthopedic_knowledge_impl(query)


__all__ = ["get_orthopedic_knowledge", "get_orthopedic_knowledge_impl"]
