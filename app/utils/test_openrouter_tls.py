"""Test OpenRouter TLS 1.2/1.3 cipher fix."""

import os
import ssl
import httpx
from openai import OpenAI
from app.utils.paths import load_environment

load_environment()

def run_openrouter_tls_test():
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        print("OpenRouter key not set in .env")
        return
    print(f"Testing OpenRouter TLS cipher fix with key: {key[:15]}...")

    ssl_context = ssl.create_default_context()
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_context.set_ciphers('DEFAULT:@SECLEVEL=1')

    http_client = httpx.Client(
        verify=ssl_context,
        headers={
            "HTTP-Referer": "https://github.com/jakariya-ai-studio",
            "X-Title": "Jakariya AI Studio",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
        print("SUCCESS! OpenRouter TLS Response:")
        print(res.choices[0].message.content)
    except Exception as exc:
        print("OpenRouter TLS Error:", repr(exc))
        print("Cause:", repr(getattr(exc, "__cause__", None)))

if __name__ == "__main__":
    run_openrouter_tls_test()
