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
    assert client.needs_web_search("today's news"), "Should trigger for today's news in normal mode"
    assert client.needs_web_search("আজকের খবর কি"), "Should trigger for আজকের খবর in normal mode"

    # Test live voice mode web search bypass:
    assert not client.needs_web_search("আজকে কেমন আছো?", is_live=True), "Should NOT trigger web search in live mode for 'আজকে কেমন আছো?'"
    assert not client.needs_web_search("লাইভ কথা বলো", is_live=True), "Should NOT trigger web search in live mode for 'লাইভ কথা বলো'"
    assert not client.needs_web_search("today is a great day", is_live=True), "Should NOT trigger web search in live mode for 'today'"
    assert client.needs_web_search("ইন্টারনেটে সার্চ করো আজকের খবর", is_live=True), "Should trigger web search in live mode for explicit request"

    # 3. Test Ollama offline exclusion
    mgr = ProviderManager.instance()
    candidates = mgr._get_candidate_provider_ids(None)
    assert "ollama" not in candidates, f"Ollama should be excluded when offline: {candidates}"

    # 4. Test GroqSTT provider instantiation and properties
    from app.voice.business_logic.stt.groq_stt import GroqSTT
    groq_stt = GroqSTT()
    assert groq_stt.provider_id == "groq_stt"
    assert groq_stt.display_name == "Groq Whisper (Ultra-Fast)"
    assert groq_stt.is_available(), "GroqSTT should be available with configured GROQ_API_KEY"

    # 5. Test pipeline streaming signals
    from app.voice.business_logic.pipeline.conversation_pipeline import PipelineWorker, ConversationPipeline
    from app.voice.voice_service import VoiceService
    from app.voice.business_logic.stt.stt_registry import STTRegistry
    from app.voice.business_logic.tts.tts_registry import TTSRegistry
    svc = VoiceService(STTRegistry([groq_stt]), TTSRegistry())
    pipe = ConversationPipeline(svc)
    assert hasattr(pipe, "response_started"), "ConversationPipeline must have response_started signal"
    assert hasattr(pipe, "partial_token"), "ConversationPipeline must have partial_token signal"
    pipe.shutdown()

    print("All assertions passed successfully!")

if __name__ == "__main__":
    test_fixes()
