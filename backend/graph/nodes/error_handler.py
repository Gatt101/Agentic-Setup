from __future__ import annotations

from langchain_core.messages import AIMessage

from core.config import settings
from graph.state import AgentState


async def error_handler_node(state: AgentState) -> dict:
    error_message = state.get("error") or "Unknown orchestration error"
    iterations = state.get("iteration_count", 0)

    if iterations < settings.max_agent_iterations:
        return {
            "messages": [
                AIMessage(
                    content=(
                        f"Tool execution issue encountered ({error_message}). "
                        "Retrying with safer fallback reasoning."
                    )
                )
            ],
            "error": None,
        }

    return {
        "final_response": (
            "I ran into an internal error and could not complete the request safely. "
            "Please retry in a moment or provide simplified input."
        )
    }
