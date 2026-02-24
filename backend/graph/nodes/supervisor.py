from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import AgentState
from services.groq_llm import get_supervisor_llm
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


async def supervisor_node(state: AgentState) -> dict:
    has_image_data = bool(state.get("image_data"))
    toolset = ALL_TOOLS if has_image_data else NON_VISION_TOOLS
    llm = get_supervisor_llm().bind_tools(toolset)

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

    response = await llm.ainvoke(prompt_messages)
    called = [call.get("name", "") for call in getattr(response, "tool_calls", []) if call.get("name")]
    active_agent = _tool_to_agent(called[-1]) if called else state.get("current_agent")

    return {
        "messages": [response],
        "iteration_count": state.get("iteration_count", 0) + 1,
        "tool_calls_made": [*state.get("tool_calls_made", []), *called],
        "current_agent": active_agent,
        "error": None,
    }
