"""Data Transfer Objects for Provider Chat Responses and Stream Chunks."""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class StreamChunk:
    """Single streaming chunk emitted by provider."""
    delta: str
    reasoning_delta: Optional[str] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


@dataclass
class ChatResponse:
    """Complete non-streaming response returned by provider."""
    content: str
    reasoning_content: Optional[str] = None
    model: str = ""
    provider_id: str = ""
    finish_reason: Optional[str] = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw_response: Optional[Dict[str, Any]] = None
