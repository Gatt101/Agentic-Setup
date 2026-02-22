from __future__ import annotations

from langchain_core.tools import tool


_CONDITION_DB = {
    "colles fracture": {
        "description": "A distal radius fracture with dorsal angulation, commonly due to a fall on an outstretched hand.",
        "symptoms": ["wrist pain", "swelling", "dinner-fork deformity"],
        "treatment_options": ["immobilization", "closed reduction", "surgical fixation when unstable"],
        "prognosis": "Generally favorable with timely reduction and rehabilitation.",
    },
    "scaphoid fracture": {
        "description": "A fracture of the scaphoid bone in the wrist, often subtle on early radiographs.",
        "symptoms": ["anatomic snuffbox tenderness", "wrist pain", "grip weakness"],
        "treatment_options": ["thumb spica cast", "follow-up imaging", "screw fixation in displaced cases"],
        "prognosis": "Good, but delayed diagnosis increases nonunion risk.",
    },
}


async def lookup_orthopedic_condition_impl(condition_name: str) -> dict:
    key = condition_name.strip().lower()
    default = {
        "description": "Condition not found in local knowledge base.",
        "symptoms": ["pain", "swelling"],
        "treatment_options": ["clinical evaluation", "targeted imaging", "specialist referral"],
        "prognosis": "Depends on injury pattern and intervention timing.",
    }
    return _CONDITION_DB.get(key, default)


@tool("knowledge_lookup_orthopedic_condition")
async def lookup_orthopedic_condition(condition_name: str) -> dict:
    """Return structured orthopedic condition reference data."""
    return await lookup_orthopedic_condition_impl(condition_name)


__all__ = ["lookup_orthopedic_condition", "lookup_orthopedic_condition_impl"]
