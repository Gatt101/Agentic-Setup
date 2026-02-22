class OrthoAssistError(Exception):
    """Base exception for application-specific errors."""


class ValidationError(OrthoAssistError):
    """Raised when tool or API input is invalid."""


class ToolExecutionError(OrthoAssistError):
    """Raised when a LangChain tool fails."""


class StorageError(OrthoAssistError):
    """Raised when storage reads/writes fail."""


class AgentExecutionError(OrthoAssistError):
    """Raised when the LangGraph orchestration fails."""
