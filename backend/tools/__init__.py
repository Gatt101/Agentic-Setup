"""LangChain tool registry used by LangGraph and MCP."""

from tools.clinical import CLINICAL_TOOLS
from tools.report import REPORT_TOOLS
from tools.vision import VISION_TOOLS

ALL_TOOLS = [
    *VISION_TOOLS,
    *CLINICAL_TOOLS,
    *REPORT_TOOLS,
]

ALL_TOOL_NAMES = {tool.name for tool in ALL_TOOLS}

VISION_NAMESPACE = {tool.name for tool in VISION_TOOLS}
CT_NAMESPACE: set[str] = set()
MRI_NAMESPACE: set[str] = set()
MODALITY_NAMESPACE: set[str] = set()
IMAGE_TOOL_NAMES = VISION_NAMESPACE

__all__ = [
    "ALL_TOOLS",
    "ALL_TOOL_NAMES",
    "VISION_NAMESPACE",
    "CT_NAMESPACE",
    "MRI_NAMESPACE",
    "MODALITY_NAMESPACE",
    "IMAGE_TOOL_NAMES",
]
