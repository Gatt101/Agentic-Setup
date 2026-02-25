from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger

from graph.state import AgentState
from services.groq_llm import get_supervisor_llm
from services.chat_store import chat_store
from tools import ALL_TOOLS

SUPERVISOR_PROMPT = """You are an orthopedic AI clinical assistant.
You must reason step-by-step and use tools when required.

Rules:
1. If an image is provided, first call vision_detect_body_part.
2. After body part detection, choose vision_detect_hand_fracture or vision_detect_leg_fracture.
3. If detection confidence is low, request better image quality.
4. clinical_generate_diagnosis requires detections.
5. clinical_assess_triage requires diagnosis.
6. If triage is RED or AMBER, hospital_find_nearby_hospitals is required.
7. For text-only questions, use knowledge_* tools.
8. Generate report PDFs only when user explicitly asks for report/document.
9. Never call the same tool repeatedly with identical context.
10. Keep final clinical response concise and medically safe.
"""

NON_VISION_TOOLS = [tool for tool in ALL_TOOLS if not tool.name.startswith("vision_")]


def _tool_to_agent(tool_name: str | None) -> str | None:
    if not tool_name:
        return None
    namespace = tool_name.split("_", 1)[0]
    mapping = {
        "vision": "vision_agent",
        "clinical": "clinical_agent",
        "knowledge": "knowledge_agent",
        "report": "report_agent",
        "hospital": "hospital_agent",
    }
    return mapping.get(namespace)


def _report_requested(state: AgentState) -> bool:
    text = str(state.get("user_message") or "").lower()
    return any(keyword in text for keyword in ("report", "pdf", "document"))


def _forced_tool_call(state: AgentState) -> dict | None:
    body_part = state.get("body_part")
    detections = state.get("detections")
    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")
    report_url = state.get("report_url")

    if not body_part and state.get("image_data"):
        return {"name": "vision_detect_body_part", "args": {}}

    if body_part in {"hand", "leg"} and detections is None:
        name = "vision_detect_hand_fracture" if body_part == "hand" else "vision_detect_leg_fracture"
        return {"name": name, "args": {}}

    if detections is not None and not diagnosis:
        return {"name": "clinical_generate_diagnosis", "args": {}}

    if diagnosis and not triage:
        return {"name": "clinical_assess_triage", "args": {}}

    if _report_requested(state) and diagnosis and triage and not report_url:
        return {"name": "report_generate_patient_pdf", "args": {}}

    return None


async def supervisor_node(state: AgentState) -> dict:
    has_image_data = bool(state.get("image_data"))
    toolset = ALL_TOOLS if has_image_data else NON_VISION_TOOLS
    llm = get_supervisor_llm().bind_tools(toolset)
    session_id = state.get("session_id", "unknown")
    iteration = state.get("iteration_count", 0)

    messages = list(state.get("messages", []))
    if not messages and state.get("user_message"):
        messages = [HumanMessage(content=state["user_message"])]

    safety_context = SystemMessage(
        content=(
            "Already-called tools in this run: "
            + ", ".join(state.get("tool_calls_made", []))
            if state.get("tool_calls_made")
            else "No tools have been called yet in this run."
        )
    )
    image_context = SystemMessage(
        content=(
            "Valid image data is available for vision analysis."
            if has_image_data
            else "No valid image data is available in this turn. Do not call any vision_* tools."
        )
    )

    prompt_messages = [SystemMessage(content=SUPERVISOR_PROMPT), safety_context, image_context, *messages]

    forced_call = _forced_tool_call(state)
    if forced_call:
        response = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": f"forced_{iteration}_{forced_call['name']}",
                    "type": "tool_call",
                    "name": forced_call["name"],
                    "args": forced_call["args"],
                }
            ],
        )
    else:
        response = await llm.ainvoke(prompt_messages)
    called = [call.get("name", "") for call in getattr(response, "tool_calls", []) if call.get("name")]
    active_agent = _tool_to_agent(called[-1]) if called else state.get("current_agent")

    logger.info(
        "session={} iteration={} active_agent={} tool_calls={}",
        session_id,
        iteration,
        active_agent or "none",
        ",".join(called) if called else "none",
    )

    trace_event = {
        "type": "supervisor_decision",
        "iteration": iteration,
        "active_agent": active_agent or "none",
        "tool_calls": called,
    }
    try:
        await chat_store.append_trace_event(session_id, trace_event)
    except Exception:
        pass

    return {
        "messages": [response],
        "iteration_count": state.get("iteration_count", 0) + 1,
        "tool_calls_made": [*state.get("tool_calls_made", []), *called],
        "agent_trace": [*state.get("agent_trace", []), trace_event],
        "current_agent": active_agent,
        "error": None,
    }
