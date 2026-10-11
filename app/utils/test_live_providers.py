"""Live Provider Health Diagnostic Tool.

Tests live API connectivity and quota status for all 8 AI Providers.
"""

from app.utils.paths import load_environment
from app.providers.manager.provider_manager import ProviderManager
from app.providers.models.chat_request import ChatRequest, MessageContent

# Ensure .env environment variables are loaded
load_environment()


def run_live_diagnostics():
    ProviderManager.reset_instance()
    mgr = ProviderManager.instance()
    print("\n" + "=" * 80)
    print("           LIVE AI PROVIDER DIAGNOSTICS & HEALTH CHECK")
    print("=" * 80)
    print(f"{'PROVIDER NAME':<25} | {'STATUS':<15} | {'DETAILS / ERROR REASON'}")
    print("-" * 80)

    for p_id in mgr.list_providers():
        provider = mgr.get_provider(p_id)
        if not provider or not provider.validate_api_key():
            print(f"{p_id:<25} | [DISABLED]     | API Key missing in .env")
            continue

        supported_models = provider.get_supported_models()
        model_id = supported_models[0].id if supported_models else "default"

        req = ChatRequest(
            messages=[MessageContent(role="user", content="Hi")],
            model=model_id,
            max_tokens=50,
            stream=False,
        )

        try:
            res = provider.chat(req)
            if res and (res.content or res.reasoning_content):
                print(f"{p_id:<25} | [WORKING OK]   | Live response received ({res.model})")
            else:
                print(f"{p_id:<25} | [NO RESPONSE]  | Empty output from provider")
        except Exception as exc:
            err_msg = str(exc)
            if "401" in err_msg or "unauthorized" in err_msg.lower() or "invalid api key" in err_msg.lower():
                reason = "Invalid or expired API Key (401)"
            elif "402" in err_msg or "credit" in err_msg.lower() or "balance" in err_msg.lower():
                reason = "Insufficient credit balance (402)"
            elif "429" in err_msg or "quota" in err_msg.lower() or "rate limit" in err_msg.lower():
                reason = "Quota limit exceeded / Rate limited (429)"
            elif "404" in err_msg or "not found" in err_msg.lower():
                reason = "Model endpoint not found (404)"
            else:
                reason = err_msg[:45] + "..." if len(err_msg) > 45 else err_msg
            print(f"{p_id:<25} | [FAILED]       | {reason}")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_live_diagnostics()
