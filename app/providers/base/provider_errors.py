"""Unified Exception Hierarchy for Provider Ecosystem."""

from typing import Optional


class ProviderError(Exception):
    """Base exception for all AI Provider operations."""

    def __init__(
        self,
        message: str,
        provider_id: Optional[str] = None,
        status_code: Optional[int] = None,
    ):
        super().__init__(message)
        self.message = message
        self.provider_id = provider_id
        self.status_code = status_code


class AuthenticationError(ProviderError):
    """Raised when API Key is missing, invalid, or unauthorized."""



class RateLimitError(ProviderError):
    """Raised when rate limit or quota exceeded."""



class ProviderUnavailableError(ProviderError):
    """Raised when provider API endpoint is unreachable or returning 5xx server errors."""



class InvalidModelError(ProviderError):
    """Raised when the requested model is unknown or unsupported by the provider."""

