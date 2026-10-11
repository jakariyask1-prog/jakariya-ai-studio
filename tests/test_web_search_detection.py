"""Unit tests for ClaudeClient.needs_web_search() keyword detection.

These tests verify that the regex-based keyword matching:
  - Correctly triggers on real web-search queries (English & Bangla).
  - Does NOT trigger on innocent words that contain a keyword as a substring
    (e.g. "password" must not match "usd", "caprice" must not match "price").
"""

import unittest

from app.api.ClaudeClient import ClaudeClient


class NeedsWebSearchTests(unittest.TestCase):
    """Tests for the regex-based web-search keyword detector."""

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #
    def _should_trigger(self, prompt: str) -> None:
        self.assertTrue(
            ClaudeClient._WEB_PATTERN.search(prompt),
            f"Expected web-search trigger for: {prompt!r}",
        )

    def _should_not_trigger(self, prompt: str) -> None:
        self.assertFalse(
            ClaudeClient._WEB_PATTERN.search(prompt),
            f"Expected NO web-search trigger for: {prompt!r}",
        )

    # ------------------------------------------------------------------ #
    # English — should trigger                                             #
    # ------------------------------------------------------------------ #
    def test_latest_triggers(self):
        self._should_trigger("What is the latest news?")

    def test_today_triggers(self):
        self._should_trigger("What happened today?")

    def test_usd_triggers(self):
        self._should_trigger("What is the usd to bdt rate?")

    def test_bitcoin_triggers(self):
        self._should_trigger("Bitcoin price today")

    def test_weather_triggers(self):
        self._should_trigger("What is the weather in Dhaka?")

    def test_stock_triggers(self):
        self._should_trigger("Show me today's stock market")

    def test_breaking_triggers(self):
        self._should_trigger("breaking news from Bangladesh")

    def test_live_triggers(self):
        self._should_trigger("live score of Bangladesh vs India")

    def test_gold_triggers(self):
        self._should_trigger("gold price today")

    def test_crypto_triggers(self):
        self._should_trigger("crypto market update")

    def test_current_triggers(self):
        self._should_trigger("current exchange rate")

    # ------------------------------------------------------------------ #
    # English — must NOT trigger (substring false-positive guard)          #
    # ------------------------------------------------------------------ #
    def test_password_does_not_trigger_usd(self):
        """'usd' must not match inside 'password'."""
        self._should_not_trigger("How do I reset my password?")

    def test_caprice_does_not_trigger_price(self):
        """'price' must not match inside 'caprice'."""
        self._should_not_trigger("I love caprice pizza")

    def test_golden_does_not_trigger_gold(self):
        """'gold' must not match inside 'golden'."""
        self._should_not_trigger("The golden gate bridge is beautiful.")

    def test_lively_does_not_trigger_live(self):
        """'live' must not match inside 'lively'."""
        self._should_not_trigger("She has a very lively personality.")

    def test_currently_does_not_trigger_current(self):
        """'current' must not match inside 'currently'."""
        self._should_not_trigger("I am currently reading a book.")

    def test_newsroom_does_not_trigger_news(self):
        """'news' must not match inside 'newsroom'."""
        self._should_not_trigger("The newsroom is a great show.")

    def test_plain_coding_question_does_not_trigger(self):
        self._should_not_trigger("How do I reverse a list in Python?")

    def test_math_question_does_not_trigger(self):
        self._should_not_trigger("What is the integral of x squared?")

    # ------------------------------------------------------------------ #
    # Bangla — should trigger                                              #
    # ------------------------------------------------------------------ #
    def test_bangla_aaj_triggers(self):
        self._should_trigger("আজ কি কোনো ছুটি আছে?")

    def test_bangla_ajker_triggers(self):
        self._should_trigger("আজকের আবহাওয়া কেমন")

    def test_bangla_khobor_triggers(self):
        self._should_trigger("আজকের খবর কী?")

    def test_bangla_dam_triggers(self):
        self._should_trigger("সোনার দাম কত আজ")

    def test_bangla_live_triggers(self):
        self._should_trigger("লাইভ ম্যাচ দেখতে চাই")

    def test_bangla_bortoman_triggers(self):
        self._should_trigger("বর্তমান সরকার কী বলছে")

    # ------------------------------------------------------------------ #
    # Case-insensitivity                                                   #
    # ------------------------------------------------------------------ #
    def test_uppercase_today_triggers(self):
        self._should_trigger("TODAY is a good day for news")

    def test_mixed_case_bitcoin_triggers(self):
        self._should_trigger("Bitcoin price check")


    # ------------------------------------------------------------------ #
    # Pure Time queries — must NOT trigger web search                    #
    # ------------------------------------------------------------------ #
    def test_pure_time_query_bypasses_web_search(self):
        client = ClaudeClient()
        self.assertFalse(client.needs_web_search("what is the time now in bangladesh?"))
        self.assertFalse(client.needs_web_search("what time is it?"))
        self.assertFalse(client.needs_web_search("এখন কয়টা বাজে?"))
        self.assertFalse(client.needs_web_search("সময় কত?"))


if __name__ == "__main__":
    unittest.main()
