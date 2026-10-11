"""Data Transfer Objects for Provider Chat Requests."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


MessageBody = str | List[Dict[str, Any]]


@dataclass
class MessageContent:
    """Represents a single message in conversation history."""
    role: str
    content: MessageBody
    name: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ChatRequest:
    """Unified request structure sent to any provider."""
    messages: List[MessageContent]
    model: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = True
    web_search: bool = False
    additional_params: Dict[str, Any] = field(default_factory=dict)
