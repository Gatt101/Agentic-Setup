from services.groq_llm import get_fast_llm
from tools.report import REPORT_TOOLS


def build_report_agent():
    return get_fast_llm().bind_tools(REPORT_TOOLS)
