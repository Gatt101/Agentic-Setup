from services.groq_llm import get_fast_llm
from tools.knowledge import KNOWLEDGE_TOOLS


def build_knowledge_agent():
    return get_fast_llm().bind_tools(KNOWLEDGE_TOOLS)
