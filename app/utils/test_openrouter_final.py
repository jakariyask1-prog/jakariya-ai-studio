"""Final verification of OpenRouterProvider."""

from app.utils.paths import load_environment
from app.providers.implementations.openrouter_provider import OpenRouterProvider
from app.providers.models.chat_request import ChatRequest, MessageContent

load_environment()

def verify():
    p = OpenRouterProvider()
    req = ChatRequest(
        messages=[MessageContent(role="user", content="Respond with the word OK")],
        model="deepseek/deepseek-chat",
        max_tokens=10,
        stream=False,
    )
    res = p.chat(req)
    print("OPENROUTER LIVE VERIFICATION SUCCESSFUL:")
    print("Response:", res.content)

if __name__ == "__main__":
    verify()
