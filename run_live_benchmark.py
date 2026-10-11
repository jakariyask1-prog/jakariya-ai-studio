import time
import sys

# Ensure UTF-8 output
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.utils.paths import load_environment
load_environment()
from app.api.ClaudeClient import ClaudeClient

client = ClaudeClient()

test_cases = [
    ("groq", "openai/gpt-oss-120b", "কেমন আছো? দ্রুত ১ লাইনে উত্তর দাও।"),
    ("openrouter", "meta-llama/llama-3.3-70b-instruct", "Tell me a short 1-sentence joke."),
    ("google_ai_studio", "google/gemini-3.6-flash", "What is 15 * 12?"),
    ("plugsky", "plugsky-micro", "Hello! In 5 words, who are you?"),
]

print("====================================================")
print("       LIVE MULTI-PROVIDER SPEED TEST BENCHMARK      ")
print("====================================================")

results = []

for p_id, m_id, prompt in test_cases:
    print(f"\n[Testing] Provider: {p_id} | Model: {m_id}")
    print(f"[Prompt]  \"{prompt}\"")
    t0 = time.time()
    first_token_time = None
    chunks = []
    
    try:
        for chunk in client.ask_stream(prompt, model=m_id, provider_id=p_id):
            if first_token_time is None:
                first_token_time = time.time() - t0
                print(f"⚡ First Token (TTFT): {first_token_time:.2f}s")
            chunks.append(chunk)
            
        total_time = time.time() - t0
        reply = "".join(chunks).strip()
        print(f"✅ Response: \"{reply}\"")
        print(f"⏱️ Total Duration: {total_time:.2f}s")
        results.append((p_id, m_id, first_token_time, total_time, reply, True))
    except Exception as exc:
        print(f"❌ Error: {exc}")
        results.append((p_id, m_id, None, None, str(exc), False))

print("\n====================================================")
print("                   BENCHMARK SUMMARY                ")
print("====================================================")
for p_id, m_id, ttft, tot, reply, ok in results:
    status = "PASS" if ok else "FAIL"
    ttft_str = f"{ttft:.2f}s" if ttft is not None else "N/A"
    tot_str = f"{tot:.2f}s" if tot is not None else "N/A"
    print(f"{p_id:18} | {m_id:32} | TTFT: {ttft_str:6} | Total: {tot_str:6} | {status}")
print("====================================================")
