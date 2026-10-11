"""Unit tests for Ollama Local Offline AI Provider."""

from unittest.mock import MagicMock, patch
import pytest

from app.providers.implementations.ollama_provider import OllamaProvider
from app.providers.models.chat_request import ChatRequest, MessageContent
from app.providers.base.provider_errors import ProviderUnavailableError, ProviderError


def test_ollama_provider_init_and_capabilities():
    provider = OllamaProvider(base_url="http://localhost:11434/v1")
    assert provider.provider_id == "ollama"
    assert provider.name == "Ollama Local (Offline)"
    assert provider.validate_api_key() is True
    assert provider.capabilities.supports_chat is True
    assert provider.capabilities.supports_reasoning is True
    assert provider.capabilities.supports_coding is True


def test_ollama_provider_default_models():
    provider = OllamaProvider()
    models = provider.get_default_models()
    assert len(models) >= 4
    model_ids = [m.id for m in models]
    assert "llama3.3" in model_ids
    assert "qwen2.5" in model_ids


def test_ollama_provider_dynamic_model_discovery():
    provider = OllamaProvider()
    mock_client = MagicMock()
    mock_item1 = MagicMock()
    mock_item1.id = "llama3:latest"
    mock_item2 = MagicMock()
    mock_item2.id = "codellama:7b"
    mock_client.models.list.return_value.data = [mock_item1, mock_item2]

    with patch.object(provider, "_get_client", return_value=mock_client):
        models = provider.get_supported_models()
        assert len(models) == 2
        assert models[0].id == "llama3:latest"
        assert models[1].id == "codellama:7b"


def test_ollama_provider_chat_completion():
    provider = OllamaProvider()
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Hello from Ollama local model!"
    mock_choice.message.reasoning_content = None
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20
    mock_response.usage.total_tokens = 30
    mock_client.chat.completions.create.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_client):
        request = ChatRequest(
            messages=[MessageContent("user", "Hello")],
            model="ollama/llama3",
            system_prompt="You are a helpful assistant",
        )
        response = provider.chat(request)

        assert response.content == "Hello from Ollama local model!"
        assert response.provider_id == "ollama"
        assert response.total_tokens == 30


def test_ollama_provider_chat_stream():
    provider = OllamaProvider()
    mock_client = MagicMock()

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock(delta=MagicMock(content="Hello "), finish_reason=None)]
    chunk2 = MagicMock()
    chunk2.choices = [MagicMock(delta=MagicMock(content="world!"), finish_reason="stop")]

    mock_client.chat.completions.create.return_value = iter([chunk1, chunk2])

    with patch.object(provider, "_get_client", return_value=mock_client):
        request = ChatRequest(
            messages=[MessageContent("user", "Hi")],
            model="ollama/llama3",
        )
        chunks = list(provider.chat_stream(request))

        assert len(chunks) == 2
        assert chunks[0].delta == "Hello "
        assert chunks[1].delta == "world!"
        assert chunks[1].finish_reason == "stop"


def test_ollama_provider_connection_error_raises_unavailable():
    provider = OllamaProvider()
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("Connection refused to http://localhost:11434")

    with patch.object(provider, "_get_client", return_value=mock_client):
        request = ChatRequest(messages=[MessageContent("user", "Hi")], model="ollama/llama3")
        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.chat(request)
        assert "Ollama server is not running locally" in str(exc_info.value)
