"""Unit and Integration tests for Provider Failover, Health & Validation System (Master Step 3 / Phase 7.8)."""

import unittest
from typing import Generator, List
from app.providers.base.base_provider import BaseProvider
from app.providers.base.provider_capabilities import ProviderCapabilities
from app.providers.base.provider_errors import (
    ProviderError,
    AuthenticationError,
    RateLimitError,
    ProviderUnavailableError,
)
from app.providers.models.chat_request import ChatRequest, MessageContent
from app.providers.models.chat_response import ChatResponse, StreamChunk
from app.providers.models.model_info import ModelInfo
from app.providers.manager.provider_manager import ProviderManager


class FailingMockProvider(BaseProvider):
    """Mock provider that simulates API failure (RateLimit or Auth error)."""

    def __init__(self, provider_id: str, fail_error_type: str = "rate_limit"):
        super().__init__(provider_id=provider_id, name=f"Failing {provider_id}", api_key="sk-fail-key")
        self.fail_error_type = fail_error_type

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_chat=True)

    def get_supported_models(self) -> List[ModelInfo]:
        return [ModelInfo("fail-model", "Fail Model", self.provider_id)]

    def validate_api_key(self) -> bool:
        return True

    def chat(self, request: ChatRequest) -> ChatResponse:
        if self.fail_error_type == "rate_limit":
            raise RateLimitError(f"Rate limit hit on {self.provider_id}", provider_id=self.provider_id, status_code=429)
        elif self.fail_error_type == "auth":
            raise AuthenticationError(f"Auth error on {self.provider_id}", provider_id=self.provider_id, status_code=401)
        else:
            raise ProviderError(f"General error on {self.provider_id}", provider_id=self.provider_id)

    def chat_stream(self, request: ChatRequest) -> Generator[StreamChunk, None, None]:
        if self.fail_error_type == "rate_limit":
            raise RateLimitError(f"Rate limit hit on {self.provider_id}", provider_id=self.provider_id, status_code=429)
        else:
            raise ProviderError(f"General error on {self.provider_id}", provider_id=self.provider_id)


class WorkingMockProvider(BaseProvider):
    """Mock provider that successfully returns chat responses."""

    def __init__(self, provider_id: str):
        super().__init__(provider_id=provider_id, name=f"Working {provider_id}", api_key="sk-work-key")

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_chat=True)

    def get_supported_models(self) -> List[ModelInfo]:
        return [ModelInfo("work-model", "Work Model", self.provider_id)]

    def validate_api_key(self) -> bool:
        return True

    def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(content=f"Success from {self.provider_id}", model=request.model, provider_id=self.provider_id)

    def chat_stream(self, request: ChatRequest) -> Generator[StreamChunk, None, None]:
        yield StreamChunk(delta=f"Stream from {self.provider_id}")


class TestProviderFailoverSystem(unittest.TestCase):
    """Test suite for Master Step 3 Provider Failover, Health & Validation System."""

    def setUp(self):
        ProviderManager.reset_instance()

    def test_auto_initialize_registers_all_core_providers(self):
        mgr = ProviderManager.instance()
        providers = mgr.list_providers()
        self.assertGreaterEqual(len(providers), 7)
        self.assertIn("openrouter", providers)
        self.assertIn("google_ai_studio", providers)
        self.assertIn("anthropic", providers)
        self.assertIn("groq", providers)
        self.assertIn("cerebras", providers)
        self.assertIn("plugsky", providers)
        self.assertIn("ollama", providers)

    def test_chat_automatic_failover(self):
        mgr = ProviderManager()
        failing_p = FailingMockProvider("p1_failing", fail_error_type="rate_limit")
        working_p = WorkingMockProvider("p2_working")

        mgr.register_provider(failing_p, priority=1)
        mgr.register_provider(working_p, priority=2)

        req = ChatRequest(messages=[MessageContent(role="user", content="Hello")], model="test-model")

        # Request targeting failing_p should automatically failover to p2_working
        res = mgr.chat(req, provider_id="p1_failing")
        self.assertEqual(res.provider_id, "p2_working")
        self.assertEqual(res.content, "Success from p2_working")

    def test_chat_stream_automatic_failover(self):
        mgr = ProviderManager()
        failing_p = FailingMockProvider("p1_failing", fail_error_type="auth")
        working_p = WorkingMockProvider("p2_working")

        mgr.register_provider(failing_p, priority=1)
        mgr.register_provider(working_p, priority=2)

        req = ChatRequest(messages=[MessageContent(role="user", content="Hello")], model="test-model")

        # Streaming request targeting failing_p should automatically failover to p2_working
        chunks = list(mgr.chat_stream(req, provider_id="p1_failing"))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].delta, "Stream from p2_working")

    def test_failover_raises_when_all_providers_fail(self):
        mgr = ProviderManager()
        f1 = FailingMockProvider("p1", fail_error_type="rate_limit")
        f2 = FailingMockProvider("p2", fail_error_type="auth")

        mgr.register_provider(f1, priority=1)
        mgr.register_provider(f2, priority=2)

        req = ChatRequest(messages=[MessageContent(role="user", content="Hello")], model="test-model")

        with self.assertRaises(AuthenticationError):
            mgr.chat(req)


if __name__ == "__main__":
    unittest.main()
