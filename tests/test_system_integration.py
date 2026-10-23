"""Integration test suite verifying full system integration through ProviderManager (Master Step 4 / Phase 7.9)."""

import unittest
from typing import Generator, List
from unittest.mock import patch, MagicMock
from app.api.ClaudeClient import ClaudeClient
from app.providers.manager.provider_manager import ProviderManager
from app.providers.base.base_provider import BaseProvider
from app.providers.base.provider_capabilities import ProviderCapabilities
from app.providers.models.chat_request import ChatRequest
from app.providers.models.chat_response import ChatResponse, StreamChunk
from app.providers.models.model_info import ModelInfo


class IntegrationMockProvider(BaseProvider):
    """Mock provider for testing end-to-end system integration."""

    def __init__(self, provider_id: str):
        super().__init__(provider_id=provider_id, name=f"Integration {provider_id}", api_key="sk-test-key")

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_chat=True)

    def get_supported_models(self) -> List[ModelInfo]:
        return [ModelInfo(f"{self.provider_id}-model", "Test Model", self.provider_id)]

    def validate_api_key(self) -> bool:
        return True

    def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(content=f"Integrated response from {self.provider_id}", model=request.model, provider_id=self.provider_id)

    def chat_stream(self, request: ChatRequest) -> Generator[StreamChunk, None, None]:
        yield StreamChunk(delta=f"Integrated stream from {self.provider_id}")


class TestSystemIntegration(unittest.TestCase):
    """Test suite for Phase 7.9 Full System Integration."""

    def setUp(self):
        ProviderManager.reset_instance()
        self.mgr = ProviderManager.instance()
        # Overwrite providers with mocks for reliable offline integration test
        self.mgr._providers.clear()
        self.mgr.register_provider(IntegrationMockProvider("openrouter"), priority=1)
        self.mgr.register_provider(IntegrationMockProvider("google_ai_studio"), priority=2)
        self.mgr.register_provider(IntegrationMockProvider("anthropic"), priority=3)
        self.mgr.register_provider(IntegrationMockProvider("groq"), priority=4)

    def tearDown(self):
        ProviderManager.reset_instance()

    def test_claude_client_provider_resolution(self):
        client = ClaudeClient()

        p_id, m = client._resolve_provider_id("google/gemini-2.5-flash")
        self.assertEqual(p_id, "google_ai_studio")

        p_id, m = client._resolve_provider_id("groq/llama-3.3-70b-versatile")
        self.assertEqual(p_id, "groq")

        p_id, m = client._resolve_provider_id("claude-3-5-sonnet-20241022")
        self.assertEqual(p_id, "anthropic")

        p_id, m = client._resolve_provider_id("deepseek/deepseek-chat")
        self.assertEqual(p_id, "openrouter")

    def test_claude_client_delegation_to_provider_manager(self):
        client = ClaudeClient()

        # Stream test via ClaudeClient delegating to ProviderManager
        chunks = list(client.ask_stream("Hello integration", model="google/gemini-2.5-flash"))
        self.assertEqual("".join(chunks), "Integrated stream from google_ai_studio")

        # Non-streaming ask test
        response = client.ask("Hello ask", model="groq/llama-3.3-70b-versatile")
        self.assertEqual(response, "Integrated stream from groq")


if __name__ == "__main__":
    unittest.main()
