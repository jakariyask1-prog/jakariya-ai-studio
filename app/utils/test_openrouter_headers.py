"""Deep Diagnostic test for OpenRouter API."""

import json
import os
import urllib.request
from app.utils.paths import load_environment

load_environment()

def diagnose_openrouter():
    key = os.getenv("OPENROUTER_API_KEY")
    print(f"Diagnosing OpenRouter with key: {key[:15] if key else 'None'}...")

    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 10,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "https://github.com/jakariya-ai-studio",
        "X-Title": "Jakariya AI Studio",
        "Content-Type": "application/json",
        "User-Agent": "JakariyaAIStudio/1.0",
    }

    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            print("\nSUCCESS! OpenRouter Response Received:")
            print(body['choices'][0]['message']['content'])
    except Exception as exc:
        print("\nOpenRouter Error Details:")
        if hasattr(exc, "read"):
            print(exc.read().decode("utf-8"))
        else:
            print(exc)

if __name__ == "__main__":
    diagnose_openrouter()
