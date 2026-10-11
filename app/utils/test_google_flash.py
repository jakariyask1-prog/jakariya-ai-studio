"""Test Google API Key with Gemini Flash model."""

from app.utils.paths import load_environment
from app.providers.implementations.google_provider import GoogleAIStudioProvider
from app.providers.models.chat_request import ChatRequest, MessageContent

load_environment()

def test_google_flash():
    provider = GoogleAIStudioProvider()
    print("Testing Google API key with 'google/gemini-1.5-flash'...")
    req = ChatRequest(
        messages=[MessageContent(role="user", content="Hello Google Gemini!")],
        model="google/gemini-1.5-flash",
        max_tokens=50,
        stream=False,
    )
    try:
        res = provider.chat(req)
        print("SUCCESS! Google API Response:")
        print(res.content)
    except Exception as exc:
        print("ERROR testing Google Flash:")
        print(exc)

if __name__ == "__main__":
    test_google_flash()
