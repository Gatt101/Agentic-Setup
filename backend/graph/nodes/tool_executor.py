from __future__ import annotations

import json
from functools import lru_cache

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode

from graph.state import AgentState
from tools import ALL_TOOLS


@lru_cache(maxsize=1)
def get_tool_executor_node() -> ToolNode:
    return ToolNode(ALL_TOOLS)


def _coerce_tool_payload(message: ToolMessage) -> dict:
    content = message.content
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


async def tool_executor_node(state: AgentState) -> dict:
    result = await get_tool_executor_node().ainvoke(state)
    updates: dict = {}

    for message in result.get("messages", []):
        if not isinstance(message, ToolMessage):
            continue

        payload = _coerce_tool_payload(message)
        if not payload:
            continue

        if message.name == "vision_detect_body_part":
            updates["body_part"] = payload.get("body_part")
        elif message.name in {"vision_detect_hand_fracture", "vision_detect_leg_fracture"}:
            updates["detections"] = payload.get("detections", [])
        elif message.name == "clinical_generate_diagnosis":
            updates["diagnosis"] = payload
        elif message.name == "clinical_assess_triage":
            updates["triage_result"] = payload
        elif message.name == "hospital_find_nearby_hospitals":
            updates["hospitals"] = payload.get("hospitals", [])
        elif message.name in {"report_generate_patient_pdf", "report_generate_clinician_pdf"}:
            updates["report_url"] = payload.get("pdf_url")

    return {**result, **updates}
