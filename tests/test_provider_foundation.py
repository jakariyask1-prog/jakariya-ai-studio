"""Unit tests for Phase 7.1 Provider Foundation Architecture."""

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
from app.providers.base.provider_types import ProviderId, Role
from app.providers.models.chat_request import ChatRequest, MessageContent
from app.providers.models.chat_response import ChatResponse, StreamChunk
from app.providers.models.model_info import ModelInfo
from app.providers.manager.provider_registry import ProviderRegistry, ProviderMeta
from app.providers.manager.health_service import ProviderHealthService, HealthStatus
from app.providers.manager.provider_manager import ProviderManager


class DummyMockProvider(BaseProvider):
    """Mock implementation of BaseProvider for foundation contract testing."""

    def __init__(self, provider_id: str = "mock_provider", api_key: str | None = "sk-valid-123"):
        super().__init__(provider_id=provider_id, name="Mock Provider", api_key=api_key)

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_chat=True, supports_reasoning=True)

    def get_supported_models(self) -> List[ModelInfo]:
        return [
            ModelInfo(
                id="mock-model-v1",
                name="Mock Model V1",
                provider_id=self.provider_id,
            )
        ]

    def validate_api_key(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("sk-valid"))

    def chat(self, request: ChatRequest) -> ChatResponse:
        if not self.validate_api_key():
            raise AuthenticationError("Invalid API key", provider_id=self.provider_id)
        return ChatResponse(
            content=f"Response to: {request.messages[-1].content}",
            model=request.model,
            provider_id=self.provider_id,
        )

    def chat_stream(self, request: ChatRequest) -> Generator[StreamChunk, None, None]:
        if not self.validate_api_key():
            raise AuthenticationError("Invalid API key", provider_id=self.provider_id)
        yield StreamChunk(delta="Hello ")
        yield StreamChunk(delta="world!")


class TestProviderFoundation(unittest.TestCase):
    """Test suite verifying Phase 7.1 Provider Foundation Architecture."""

    def setUp(self):
        ProviderRegistry.clear()
        ProviderManager.reset_instance()

    def test_base_provider_contract(self):
        mock_p = DummyMockProvider(api_key="sk-valid-999")
        self.assertEqual(mock_p.provider_id, "mock_provider")
        self.assertTrue(mock_p.validate_api_key())
        self.assertTrue(mock_p.capabilities.supports_chat)
        self.assertTrue(mock_p.capabilities.supports_reasoning)
        self.assertEqual(len(mock_p.get_supported_models()), 1)

    def test_chat_request_and_response_models(self):
        req = ChatRequest(
            messages=[MessageContent(role=Role.USER.value, content="Hello AI")],
            model="mock-model-v1",
            temperature=0.5,
        )
        self.assertEqual(req.messages[0].content, "Hello AI")
        self.assertEqual(req.model, "mock-model-v1")

        resp = ChatResponse(content="AI response", model="mock-model-v1", provider_id="mock_provider")
        self.assertEqual(resp.content, "AI response")

    def test_error_hierarchy(self):
        err = AuthenticationError("Key expired", provider_id="google", status_code=401)
        self.assertIsInstance(err, ProviderError)
        self.assertEqual(err.status_code, 401)
        self.assertEqual(err.provider_id, "google")

    def test_provider_registry(self):
        meta = ProviderMeta(
            id=ProviderId.GOOGLE.value,
            name="Google AI Studio",
            default_base_url="https://generativelanguage.googleapis.com",
            capabilities=ProviderCapabilities(supports_vision=True),
            models=[ModelInfo(id="gemini-2.5-pro", name="Gemini 2.5 Pro", provider_id="google_ai_studio")],
        )
        ProviderRegistry.register_provider(meta)
        self.assertIn("google_ai_studio", ProviderRegistry.get_provider_ids())
        self.assertEqual(len(ProviderRegistry.get_all_models()), 1)

    def test_health_service(self):
        self.assertEqual(ProviderHealthService.evaluate_status(None), HealthStatus.NO_API_KEY)
        self.assertEqual(ProviderHealthService.evaluate_status(""), HealthStatus.NO_API_KEY)
        self.assertEqual(ProviderHealthService.evaluate_status("sk-123", enabled=False), HealthStatus.DISABLED)
        self.assertEqual(ProviderHealthService.evaluate_status("sk-123", enabled=True), HealthStatus.READY)

    def test_provider_manager_dispatch(self):
        mgr = ProviderManager()
        valid_p = DummyMockProvider("p1", api_key="sk-valid-1")
        invalid_p = DummyMockProvider("p2", api_key="invalid-key")

        mgr.register_provider(valid_p, priority=1)
        mgr.register_provider(invalid_p, priority=2)

        req = ChatRequest(messages=[MessageContent(role="user", content="Test")], model="mock-model-v1")

        # Explicit provider dispatch
        resp = mgr.chat(req, provider_id="p1")
        self.assertEqual(resp.content, "Response to: Test")

        # Stream dispatch
        chunks = list(mgr.chat_stream(req, provider_id="p1"))
        full_text = "".join(c.delta for c in chunks)
        self.assertEqual(full_text, "Hello world!")

        # Priority fallback resolution skips invalid_p and picks valid_p
        candidates = mgr._get_candidate_provider_ids(provider_id="p2")
        self.assertEqual(candidates[0], "p1")

    def test_provider_manager_raises_when_no_provider_available(self):
        mgr = ProviderManager()
        invalid_p = DummyMockProvider("p2", api_key="invalid-key")
        mgr.register_provider(invalid_p)

        req = ChatRequest(messages=[MessageContent(role="user", content="Test")], model="mock-model-v1")
        with self.assertRaises(AuthenticationError):
            mgr.chat(req)


if __name__ == "__main__":
    unittest.main()
