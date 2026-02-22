from __future__ import annotations

from langchain_core.messages import AIMessage

from graph.state import AgentState


def _last_non_tool_ai_message(state: AgentState) -> str | None:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None):
            content = message.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [part.get("text", "") for part in content if isinstance(part, dict)]
                return " ".join(part for part in parts if part).strip() or None
    return None


async def response_builder_node(state: AgentState) -> dict:
    if state.get("final_response"):
        return {}

    ai_message = _last_non_tool_ai_message(state)
    if ai_message:
        return {"final_response": ai_message}

    diagnosis = state.get("diagnosis")
    triage = state.get("triage_result")
    hospitals = state.get("hospitals")

    if diagnosis:
        response = f"Finding: {diagnosis.get('finding', 'N/A')} (severity: {diagnosis.get('severity', 'N/A')})."
        if triage:
            response += f" Triage level is {triage.get('level', 'N/A')}."
        if hospitals:
            response += f" Found {len(hospitals)} nearby hospital options."
        response += " Please confirm with a licensed clinician."
        return {"final_response": response}

    return {
        "final_response": (
            "I could not complete a full analysis from the provided data. "
            "Please share clearer details or a higher quality image."
        )
    }
