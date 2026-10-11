"""Abstract Base Tool Interface for AI Agent with Metadata & Permission Model."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PermissionLevel(str, Enum):
    """Permission level safety classification for agent tools."""

    READ_ONLY = "read_only"
    REQUIRES_APPROVAL = "requires_approval"
    UNSANDBOXED = "unsandboxed"


@dataclass
class ToolMetadata:
    """Detailed metadata schema exposed by every AI Agent tool."""

    name: str
    description: str
    version: str = "1.0.0"
    permission: PermissionLevel = PermissionLevel.READ_ONLY
    supported_file_types: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Output structure returned by a tool execution."""

    success: bool
    output: str
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    execution_time_ms: float = 0.0


class BaseTool(ABC):
    """Abstract Base Class for all AI Agent tools enforcing metadata and permission rules."""

    def __init__(
        self,
        name: str,
        description: str,
        permission_level: PermissionLevel = PermissionLevel.READ_ONLY,
        version: str = "1.0.0",
        supported_file_types: Optional[List[str]] = None,
        capabilities: Optional[List[str]] = None,
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.description = description
        self.permission_level = permission_level
        self.enabled = True

        self.metadata = ToolMetadata(
            name=name,
            description=description,
            version=version,
            permission=permission_level,
            supported_file_types=supported_file_types or [],
            capabilities=capabilities or [],
            input_schema=input_schema or {},
            output_schema=output_schema or {},
        )

    def requires_approval(self) -> bool:
        """Return True if executing this tool requires explicit user confirmation."""
        return self.permission_level in (
            PermissionLevel.REQUIRES_APPROVAL,
            PermissionLevel.UNSANDBOXED,
        )

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool action with given parameters."""
