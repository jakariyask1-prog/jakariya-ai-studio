"""Test Google Gemini REST API natively."""

import json
import urllib.request
from app.utils.paths import load_environment
import os

load_environment()

def run_google_native_test():
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        print("Gemini API key not set in .env")
        return
    print(f"Testing Google Native REST API with key: {key[:8]}...")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": "Hello Gemini!"}]}]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            print("SUCCESS Native Google API Response:")
            text = body['candidates'][0]['content']['parts'][0]['text']
            print(text)
    except Exception as exc:
        print("Google Native Error:")
        print(exc)

if __name__ == "__main__":
    run_google_native_test()
