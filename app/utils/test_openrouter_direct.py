"""Test OpenRouter API Key directly."""

from app.utils.paths import load_environment
from app.providers.implementations.openrouter_provider import OpenRouterProvider
from app.providers.models.chat_request import ChatRequest, MessageContent

load_environment()

def test_openrouter():
    provider = OpenRouterProvider()
    print("Testing OpenRouter API key...")
    req = ChatRequest(
        messages=[MessageContent(role="user", content="Hi OpenRouter")],
        model="deepseek/deepseek-chat",
        max_tokens=10,
        stream=False,
    )
    try:
        res = provider.chat(req)
        print("SUCCESS! OpenRouter Response:")
        print(res.content)
    except Exception as exc:
        print("OpenRouter Error:")
        print(exc)

if __name__ == "__main__":
    test_openrouter()
