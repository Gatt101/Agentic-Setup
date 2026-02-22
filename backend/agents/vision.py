from services.groq_llm import get_fast_llm
from tools.vision import VISION_TOOLS


def build_vision_agent():
    return get_fast_llm().bind_tools(VISION_TOOLS)
