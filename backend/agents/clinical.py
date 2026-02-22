from services.groq_llm import get_supervisor_llm
from tools.clinical import CLINICAL_TOOLS


def build_clinical_agent():
    return get_supervisor_llm().bind_tools(CLINICAL_TOOLS)
