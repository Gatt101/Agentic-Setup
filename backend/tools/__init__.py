"""LangChain tool registry used by LangGraph and MCP."""

from tools.clinical import CLINICAL_TOOLS
from tools.hospital import HOSPITAL_TOOLS
from tools.knowledge import KNOWLEDGE_TOOLS
from tools.report import REPORT_TOOLS
from tools.vision import VISION_TOOLS

ALL_TOOLS = [
    *VISION_TOOLS,
    *CLINICAL_TOOLS,
    *KNOWLEDGE_TOOLS,
    *REPORT_TOOLS,
    *HOSPITAL_TOOLS,
]

ALL_TOOL_NAMES = {tool.name for tool in ALL_TOOLS}

__all__ = ["ALL_TOOLS", "ALL_TOOL_NAMES"]
