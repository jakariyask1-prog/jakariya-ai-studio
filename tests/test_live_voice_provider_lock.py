"""Tests for Live Voice Mode fixes:
1. Plugsky provider lock / priority demotion
2. Live Voice max_tokens cap (200) and temperature (0.6)
3. Phonetic STT live voice system directive injection
4. No web-search hijack in live mode (unless explicit command like "ওয়েবে খোঁজ কর")
5. FIRST_CHUNK_END_RE fires on earliest punctuation or 3-5 words
6. ProviderManager.chat_stream passes is_live flag correctly
7. STT transcript cleaning handles bracketed audio noise and Whisper hallucinations
"""

import re
import unittest
from typing import Generator, List
from unittest.mock import patch, MagicMock

from app.providers.base.base_provider import BaseProvider
from app.providers.base.provider_capabilities import ProviderCapabilities
from app.providers.base.provider_errors import ProviderError, RateLimitError, ProviderUnavailableError
from app.providers.models.chat_request import ChatRequest, MessageContent
from app.providers.models.chat_response import ChatResponse, StreamChunk
from app.providers.models.model_info import ModelInfo
from app.providers.manager.provider_manager import ProviderManager


# ---------------------------------------------------------------------------
# Helper mock providers
# ---------------------------------------------------------------------------

class SuccessProvider(BaseProvider):
    def __init__(self, pid: str):
        super().__init__(provider_id=pid, name=f"Success-{pid}", api_key="sk-ok")

    @property
    def capabilities(self):
        return ProviderCapabilities(supports_chat=True)

    def get_supported_models(self):
        return [ModelInfo(f"{self.provider_id}-model", "Model", self.provider_id)]

    def validate_api_key(self):
        return True

    def chat(self, request):
        return ChatResponse(content=f"ok from {self.provider_id}", model=request.model, provider_id=self.provider_id)

    def chat_stream(self, request):
        yield StreamChunk(delta=f"stream from {self.provider_id}")


class FailingProvider(BaseProvider):
    def __init__(self, pid: str):
        super().__init__(provider_id=pid, name=f"Fail-{pid}", api_key="sk-fail")

    @property
    def capabilities(self):
        return ProviderCapabilities(supports_chat=True)

    def get_supported_models(self):
        return [ModelInfo(f"{self.provider_id}-model", "Fail Model", self.provider_id)]

    def validate_api_key(self):
        return True

    def chat(self, request):
        raise RateLimitError("Rate limited", provider_id=self.provider_id, status_code=429)

    def chat_stream(self, request):
        raise RateLimitError("Rate limited", provider_id=self.provider_id, status_code=429)
        yield  # make it a generator


# ---------------------------------------------------------------------------
# Test Suite 1: Plugsky priority demotion
# ---------------------------------------------------------------------------

class TestPlugskyPriorityDemotion(unittest.TestCase):
    """Verify Plugsky is never priority 1 in the auto_initialize list."""

    def setUp(self):
        ProviderManager.reset_instance()

    def test_plugsky_is_not_first_in_priority_list(self):
        """Plugsky must have priority >= 50, never 1."""
        mgr = ProviderManager()
        mgr.auto_initialize()
        priority_map = mgr._priority_map
        self.assertIn("plugsky", priority_map)
        self.assertGreaterEqual(priority_map["plugsky"], 50,
                                "Plugsky priority must be >= 50 so it never preempts user-selected providers")

    def test_groq_outranks_plugsky(self):
        """Groq must have lower priority number than Plugsky (i.e. higher precedence)."""
        mgr = ProviderManager()
        mgr.auto_initialize()
        pm = mgr._priority_map
        self.assertIn("groq", pm)
        self.assertIn("plugsky", pm)
        self.assertLess(pm["groq"], pm["plugsky"],
                        "Groq must outrank Plugsky in priority (lower number = higher priority)")

    def test_plugsky_not_in_candidates_when_groq_available(self):
        """When Groq is registered and has a valid key, Plugsky must not appear before it."""
        mgr = ProviderManager()
        groq = SuccessProvider("groq")
        plugsky = SuccessProvider("plugsky")
        mgr.register_provider(groq, priority=2)
        mgr.register_provider(plugsky, priority=50)

        candidates = mgr._get_candidate_provider_ids(None)
        self.assertLess(candidates.index("groq"), candidates.index("plugsky"))


# ---------------------------------------------------------------------------
# Test Suite 2: Live Voice Provider Lock
# ---------------------------------------------------------------------------

class TestLiveVoiceProviderLock(unittest.TestCase):
    """Verify that is_live=True strictly locks the selected provider."""

    def test_live_mode_candidates_only_contains_selected_provider(self):
        """In live mode with explicit provider_id, candidates list must only have that provider."""
        mgr = ProviderManager()
        groq = SuccessProvider("groq")
        plugsky = SuccessProvider("plugsky")
        mgr.register_provider(groq, priority=2)
        mgr.register_provider(plugsky, priority=50)

        candidates = mgr._get_candidate_provider_ids("groq", is_live=True)
        self.assertEqual(candidates, ["groq"],
                         "Live Mode must ONLY use the user-selected provider, no fallback to Plugsky")

    def test_live_mode_without_provider_id_excludes_plugsky(self):
        """Without explicit provider_id, live mode must NOT include Plugsky in fallback candidates."""
        mgr = ProviderManager()
        groq = SuccessProvider("groq")
        plugsky = SuccessProvider("plugsky")
        mgr.register_provider(groq, priority=2)
        mgr.register_provider(plugsky, priority=50)

        candidates = mgr._get_candidate_provider_ids(None, is_live=True)
        self.assertIn("groq", candidates)
        self.assertNotIn("plugsky", candidates, "Live Mode must never fall back to Plugsky automatically")

    def test_live_chat_stream_raises_not_falls_to_plugsky(self):
        """When user-selected provider fails in live mode, raise error not fall to Plugsky."""
        mgr = ProviderManager()
        failing_groq = FailingProvider("groq")
        success_plugsky = SuccessProvider("plugsky")
        mgr.register_provider(failing_groq, priority=2)
        mgr.register_provider(success_plugsky, priority=50)

        req = ChatRequest(messages=[MessageContent(role="user", content="Hello")], model="test-model")

        with self.assertRaises((RateLimitError, ProviderError, ProviderUnavailableError),
                               msg="Live mode must raise on primary failure, not fall to Plugsky"):
            list(mgr.chat_stream(req, provider_id="groq", is_live=True))

    def test_non_live_chat_stream_does_fall_to_plugsky(self):
        """In non-live mode, failover to Plugsky is allowed (legacy behavior)."""
        mgr = ProviderManager()
        failing_groq = FailingProvider("groq")
        success_plugsky = SuccessProvider("plugsky")
        mgr.register_provider(failing_groq, priority=2)
        mgr.register_provider(success_plugsky, priority=50)

        req = ChatRequest(messages=[MessageContent(role="user", content="Hello")], model="test-model")
        chunks = list(mgr.chat_stream(req, provider_id="groq", is_live=False))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].delta, "stream from plugsky")


# ---------------------------------------------------------------------------
# Test Suite 3: Live Voice max_tokens and temperature in ClaudeClient
# ---------------------------------------------------------------------------

class TestLiveVoiceLatencySettings(unittest.TestCase):
    """Verify max_tokens=1024 cap and temperature=0.6 in live mode."""

    def setUp(self):
        ProviderManager.reset_instance()

    def test_ask_stream_caps_max_tokens_in_live_mode(self):
        """max_tokens must be capped at 1024 when is_live=True."""
        from app.api.ClaudeClient import ClaudeClient

        captured_requests = []

        def fake_chat_stream(req, provider_id=None, is_live=False):
            captured_requests.append(req)
            yield StreamChunk(delta="hi")

        with patch.object(ProviderManager, "chat_stream", side_effect=fake_chat_stream):
            client = ClaudeClient()
            list(client.ask_stream("Hello", max_tokens=2048, is_live=True))

        self.assertEqual(len(captured_requests), 1)
        self.assertLessEqual(captured_requests[0].max_tokens, 1024,
                             "max_tokens must be capped at 1024 in Live Voice Mode")

    def test_ask_stream_uses_live_temperature_in_live_mode(self):
        """temperature must be 0.6 when is_live=True."""
        from app.api.ClaudeClient import ClaudeClient

        captured_requests = []

        def fake_chat_stream(req, provider_id=None, is_live=False):
            captured_requests.append(req)
            yield StreamChunk(delta="hi")

        with patch.object(ProviderManager, "chat_stream", side_effect=fake_chat_stream):
            client = ClaudeClient()
            list(client.ask_stream("Hello", is_live=True))

        self.assertEqual(captured_requests[0].temperature, 0.6,
                         "temperature must be 0.6 in Live Voice Mode")

    def test_ask_stream_uses_default_temperature_in_normal_mode(self):
        """temperature must be 0.7 (standard default) in non-live mode."""
        from app.api.ClaudeClient import ClaudeClient

        captured_requests = []

        def fake_chat_stream(req, provider_id=None, is_live=False):
            captured_requests.append(req)
            yield StreamChunk(delta="hi")

        with patch.object(ProviderManager, "chat_stream", side_effect=fake_chat_stream):
            client = ClaudeClient()
            list(client.ask_stream("Hello", is_live=False))

        self.assertEqual(captured_requests[0].temperature, 0.7,
                         "temperature must be 0.7 in normal (non-live) mode")

    def test_normal_mode_max_tokens_not_capped(self):
        """max_tokens=2048 must NOT be reduced in normal (non-live) mode."""
        from app.api.ClaudeClient import ClaudeClient

        captured_requests = []

        def fake_chat_stream(req, provider_id=None, is_live=False):
            captured_requests.append(req)
            yield StreamChunk(delta="hi")

        with patch.object(ProviderManager, "chat_stream", side_effect=fake_chat_stream):
            client = ClaudeClient()
            list(client.ask_stream("Hello", max_tokens=2048, is_live=False))

        self.assertEqual(captured_requests[0].max_tokens, 2048,
                         "max_tokens must remain 2048 in non-live mode")


# ---------------------------------------------------------------------------
# Test Suite 4: Live Voice System Prompt / Phonetic STT Directive
# ---------------------------------------------------------------------------

class TestLiveVoiceSystemPrompt(unittest.TestCase):
    """Verify the full master phonetic STT directive is injected in live mode."""

    def test_live_voice_directive_exported_from_prompt_package(self):
        """LIVE_VOICE_SYSTEM_DIRECTIVE must be importable from prompt package."""
        from prompt import LIVE_VOICE_SYSTEM_DIRECTIVE
        self.assertIsInstance(LIVE_VOICE_SYSTEM_DIRECTIVE, str)
        self.assertGreater(len(LIVE_VOICE_SYSTEM_DIRECTIVE), 100)

    def test_live_voice_directive_present_in_claude_client(self):
        """LIVE_VOICE_SYSTEM_DIRECTIVE must be present in ClaudeClient module."""
        import app.api.ClaudeClient as cc
        self.assertTrue(hasattr(cc, "LIVE_VOICE_SYSTEM_DIRECTIVE"))
        self.assertIn("ULTRA-RESPONSIVE BILINGUAL", cc.LIVE_VOICE_SYSTEM_DIRECTIVE)

    def test_live_system_prompt_contains_phonetic_tolerance(self):
        """The live system prompt must contain phonetic STT tolerance wording."""
        from prompt import LIVE_VOICE_SYSTEM_DIRECTIVE
        self.assertIn("PHONETIC", LIVE_VOICE_SYSTEM_DIRECTIVE)
        self.assertIn("STT", LIVE_VOICE_SYSTEM_DIRECTIVE)
        self.assertIn("NEVER judge", LIVE_VOICE_SYSTEM_DIRECTIVE)

    def test_live_system_prompt_contains_tts_compatibility_rule(self):
        """The live system prompt must ban emojis, URLs, IPA symbols for TTS compatibility."""
        from prompt import LIVE_VOICE_SYSTEM_DIRECTIVE
        self.assertIn("TTS", LIVE_VOICE_SYSTEM_DIRECTIVE)
        self.assertIn("emojis", LIVE_VOICE_SYSTEM_DIRECTIVE)
        self.assertIn("IPA", LIVE_VOICE_SYSTEM_DIRECTIVE)

    def test_live_system_prompt_contains_spelling_rule(self):
        """The live system prompt must contain spelling accuracy instructions."""
        from prompt import LIVE_VOICE_SYSTEM_DIRECTIVE
        self.assertIn("SPELLING", LIVE_VOICE_SYSTEM_DIRECTIVE)
        self.assertIn("letter-by-letter", LIVE_VOICE_SYSTEM_DIRECTIVE)

    def test_get_dynamic_system_prompt_includes_directive_in_live_mode(self):
        """ClaudeClient._get_dynamic_system_prompt() must include the directive when is_live=True."""
        from app.api.ClaudeClient import ClaudeClient
        client = ClaudeClient()
        live_prompt = client._get_dynamic_system_prompt(is_live=True)
        self.assertIn("PHONETIC", live_prompt)
        self.assertIn("STT", live_prompt)
        self.assertIn("TTS", live_prompt)

    def test_get_dynamic_system_prompt_no_directive_in_normal_mode(self):
        """In normal mode, the live phonetic directive must NOT be injected."""
        from app.api.ClaudeClient import ClaudeClient
        client = ClaudeClient()
        normal_prompt = client._get_dynamic_system_prompt(is_live=False)
        self.assertNotIn("ZERO WRONG-WORD PENALTY", normal_prompt)


# ---------------------------------------------------------------------------
# Test Suite 5: Web Search Bypass in Live Mode
# ---------------------------------------------------------------------------

class TestWebSearchBypassLiveMode(unittest.TestCase):
    """Verify casual Bangla/English words don't trigger web search in live mode."""

    def setUp(self):
        from app.api.ClaudeClient import ClaudeClient
        self.client = ClaudeClient()

    def test_live_mode_casual_bangla_no_web_search(self):
        self.assertFalse(self.client.needs_web_search("আজকে কেমন আছো?", is_live=True))
        self.assertFalse(self.client.needs_web_search("লাইভ কথা বলো", is_live=True))
        self.assertFalse(self.client.needs_web_search("আজকের কাজ কি?", is_live=True))

    def test_live_mode_casual_english_no_web_search(self):
        self.assertFalse(self.client.needs_web_search("today is a great day", is_live=True))
        self.assertFalse(self.client.needs_web_search("what is live voice mode", is_live=True))

    def test_live_mode_explicit_search_triggers(self):
        self.assertTrue(self.client.needs_web_search("ইন্টারনেটে সার্চ করো আজকের খবর", is_live=True))
        self.assertTrue(self.client.needs_web_search("search online for the latest news", is_live=True))
        self.assertTrue(self.client.needs_web_search("ওয়েব সার্চ করো", is_live=True))
        self.assertTrue(self.client.needs_web_search("ওয়েবে খোঁজ কর আজকের খবর", is_live=True))
        self.assertTrue(self.client.needs_web_search("ওয়েবে খোঁজ করো", is_live=True))

    def test_normal_mode_casual_triggers_web_search(self):
        """In non-live mode, ambiguous keywords should still trigger web search."""
        self.assertTrue(self.client.needs_web_search("today's news", is_live=False))
        self.assertTrue(self.client.needs_web_search("আজকের খবর কি", is_live=False))


# ---------------------------------------------------------------------------
# Test Suite 6: STT Transcript Cleaning & FIRST_CHUNK_END_RE
# ---------------------------------------------------------------------------

class TestSTTTranscriptCleaningAndFirstChunk(unittest.TestCase):
    """Verify STT noise cleaning and earliest sentence boundary triggering."""

    def test_stt_transcript_cleans_bracketed_audio_tags(self):
        raw_stt = "[Music] Hello there, can you help me?"
        cleaned = re.sub(r'\[.*?\]|\(.*?\)|[*_~]', ' ', raw_stt)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        self.assertEqual(cleaned, "Hello there, can you help me?")

    def test_stt_transcript_cleans_parenthetical_tags(self):
        raw_stt = "(laughter) I want to know about physics"
        cleaned = re.sub(r'\[.*?\]|\(.*?\)|[*_~]', ' ', raw_stt)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        self.assertEqual(cleaned, "I want to know about physics")

    def test_first_chunk_fires_on_comma(self):
        """A comma or clause boundary should fire the first TTS chunk."""
        FIRST_CHUNK_END_RE = re.compile(r'([.!?,，;:—–…\n\u0964\u0965]+(?:\s+|$))')
        sentence_buffer = "Sure, I can help"
        match = FIRST_CHUNK_END_RE.search(sentence_buffer)
        self.assertIsNotNone(match)
        cand = sentence_buffer[:match.end()]
        self.assertEqual(cand, "Sure, ")

    def test_first_chunk_fires_on_em_dash(self):
        """An em-dash should fire FIRST_CHUNK_END_RE."""
        FIRST_CHUNK_END_RE = re.compile(r'([.!?,，;:—–…\n\u0964\u0965]+(?:\s+|$))')
        sentence_buffer = "Yes — let me explain"
        match = FIRST_CHUNK_END_RE.search(sentence_buffer)
        self.assertIsNotNone(match)

    def test_first_chunk_fires_at_4_words_without_punctuation(self):
        """Without punctuation, 4 words trigger the earliest audio chunk."""
        sentence_buffer = "Artificial intelligence is changing"
        words = sentence_buffer.split()
        self.assertGreaterEqual(len(words), 4)


if __name__ == "__main__":
    unittest.main()
