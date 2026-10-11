"""Test OpenRouter with detailed exception printing."""

import os
import certifi
import httpx
from openai import OpenAI
from app.utils.paths import load_environment

load_environment()

def run_openrouter_ssl_test():
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        print("OpenRouter key not set in .env")
        return
    print(f"Testing OpenRouter with key: {key[:15]}...")

    http_client = httpx.Client(
        verify=certifi.where(),
        headers={
            "HTTP-Referer": "https://github.com/jakariya-ai-studio",
            "X-Title": "Jakariya AI Studio",
        }
    )

    client = OpenAI(
        api_key=key,
        base_url="https://openrouter.ai/api/v1",
        http_client=http_client,
    )

    try:
        res = client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[{"role": "user", "content": "Hello OpenRouter"}],
            max_tokens=10,
        )
        print("SUCCESS! OpenRouter SSL Response:")
        print(res.choices[0].message.content)
    except Exception as exc:
        print("OpenRouter SSL Error repr:", repr(exc))
        print("Cause:", repr(getattr(exc, "__cause__", None)))

if __name__ == "__main__":
    run_openrouter_ssl_test()
