from services.groq_llm import get_fast_llm
from tools.hospital import HOSPITAL_TOOLS


def build_hospital_agent():
    return get_fast_llm().bind_tools(HOSPITAL_TOOLS)
