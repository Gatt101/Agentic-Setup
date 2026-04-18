"""LangChain tool registry used by LangGraph and MCP."""

from tools.clinical import CLINICAL_TOOLS
from tools.ct import CT_TOOLS
from tools.hospital import HOSPITAL_TOOLS
from tools.knowledge import KNOWLEDGE_TOOLS
from tools.modality import MODALITY_TOOLS
from tools.mri import MRI_TOOLS
from tools.report import REPORT_TOOLS
from tools.vision import VISION_TOOLS

ALL_TOOLS = [
    *MODALITY_TOOLS,
    *VISION_TOOLS,
    *CT_TOOLS,
    *MRI_TOOLS,
    *CLINICAL_TOOLS,
    *KNOWLEDGE_TOOLS,
    *REPORT_TOOLS,
    *HOSPITAL_TOOLS,
]

ALL_TOOL_NAMES = {tool.name for tool in ALL_TOOLS}

VISION_NAMESPACE = {tool.name for tool in VISION_TOOLS}
CT_NAMESPACE = {tool.name for tool in CT_TOOLS}
MRI_NAMESPACE = {tool.name for tool in MRI_TOOLS}
MODALITY_NAMESPACE = {tool.name for tool in MODALITY_TOOLS}
IMAGE_TOOL_NAMES = VISION_NAMESPACE | CT_NAMESPACE | MRI_NAMESPACE | MODALITY_NAMESPACE

__all__ = [
    "ALL_TOOLS",
    "ALL_TOOL_NAMES",
    "VISION_NAMESPACE",
    "CT_NAMESPACE",
    "MRI_NAMESPACE",
    "MODALITY_NAMESPACE",
    "IMAGE_TOOL_NAMES",
]
