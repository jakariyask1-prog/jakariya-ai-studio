"""Test OpenRouter with free model slugs."""

from app.utils.paths import load_environment
from app.providers.implementations.openrouter_provider import OpenRouterProvider
from app.providers.models.chat_request import ChatRequest, MessageContent

load_environment()

def test_openrouter_free():
    provider = OpenRouterProvider()
    print("Testing OpenRouter with 'meta-llama/llama-3.3-70b-instruct:free'...")
    req = ChatRequest(
        messages=[MessageContent(role="user", content="Hi OpenRouter!")],
        model="meta-llama/llama-3.3-70b-instruct:free",
        max_tokens=20,
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
    test_openrouter_free()
