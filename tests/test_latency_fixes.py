import sys
import time

from app.api.ClaudeClient import ClaudeClient
from app.providers.manager.provider_manager import ProviderManager

def test_fixes():
    client = ClaudeClient()
    
    # 1. Test model resolution
    p_id, norm_model = client._resolve_provider_id("plugsky-lite")
    assert p_id == "plugsky", f"Expected plugsky, got {p_id}"
    assert norm_model == "plugsky-lite"

    p_id_google, _ = client._resolve_provider_id("google/gemini-3.6-flash")
    assert p_id_google == "google_ai_studio"

    # 2. Test web search triggers
    assert not client.needs_web_search("find the bug in this code"), "Should NOT trigger web search for 'find'"
    assert not client.needs_web_search("ai answer very slow why find it first?"), "Should NOT trigger web search"
    assert not client.needs_web_search("এখন কি করব"), "Should NOT trigger web search for conversational Bengali"
    assert client.needs_web_search("today's news"), "Should trigger for today's news"
    assert client.needs_web_search("আজকের খবর কি"), "Should trigger for আজকের খবর"

    # 3. Test Ollama offline exclusion
    mgr = ProviderManager.instance()
    candidates = mgr._get_candidate_provider_ids(None)
    assert "ollama" not in candidates, f"Ollama should be excluded when offline: {candidates}"

    print("All assertions passed successfully!")

if __name__ == "__main__":
    test_fixes()
