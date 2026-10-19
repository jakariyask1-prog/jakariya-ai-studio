"""Unified Multi-Model AI Client delegating directly to ProviderManager ecosystem."""

import re
import logging
from collections.abc import Sequence
from typing import Any

from prompt import SYSTEM_PROMPT, PROFILE_PROMPT
from app.utils.paths import load_environment
from app.providers.manager.provider_manager import ProviderManager
from app.providers.models.chat_request import ChatRequest, MessageContent
from .tavily_client import WebSearch
from .model_catalog import DEFAULT_MODEL

load_environment()


class ClaudeClient:
    """
    Unified Multi-Model AI Client delegating directly to ProviderManager ecosystem.
    Supports OpenRouter, Google AI Studio, Anthropic, Groq, Cerebras, GitHub Models,
    Mistral, and Kimi AI with multi-turn conversation, web search, and streaming.
    """

    DEFAULT_MODEL = DEFAULT_MODEL

    _ENGLISH_KEYWORDS = [
        "web search", "google search", "search web", "search online", "search the web",
        "search the internet", "latest news", "breaking news", "current weather",
        "weather forecast", "weather in", "live score", "match score", "stock price",
        "share price", "crypto price", "bitcoin price", "gold price", "usd to bdt",
        "exchange rate", "currency rate", "realtime", "real-time", "real time data",
        "live update", "today's news", "weather", "crypto", "bitcoin", "forecast",
        "who is the current president", "who is the current prime minister",
        "who is the prime minister of", "who is the president of",
        "today", "stock", "news", "current", "live", "gold", "usd", "price", "latest",
    ]

    _BANGLA_KEYWORDS = [
        "আজকের খবর", "আজকের সংবাদ", "তাজা খবর", "ব্রেকিং নিউজ", "আবহাওয়া",
        "আবহাওয়ার খবর", "তাপমাত্রা", "লাইভ স্কোর", "খেলার স্কোর", "সোনার দাম",
        "ডলারের দাম", "ডলার রেট", "টাকার রেট", "মুদ্রার হার", "শেয়ার বাজার",
        "ক্রিপ্টো", "অনলাইন সার্চ", "ওয়েব সার্চ", "অনুসন্ধান করুন",
        "ইন্টারনেটে খুঁজুন", "লাইভ আপডেট", "বাস্তব সময়",
        "আজ", "আজকে", "বর্তমান", "লাইভ", "খবর", "সংবাদ", "দাম",
    ]

    _WEB_PATTERN: re.Pattern = re.compile(
        r'(?:\b(?:' + '|'.join(re.escape(k) for k in _ENGLISH_KEYWORDS) + r')\b)'
        r'|'
        r'(?:(?:^|(?<=\s))(?:' + '|'.join(re.escape(k) for k in _BANGLA_KEYWORDS) + r')(?=[\s\.,?!;:।\u0964]|$))',
        re.IGNORECASE,
    )

    _PURE_TIME_PATTERN: re.Pattern = re.compile(
        r'^\s*(?:'
        r'what\s+(?:is\s+)?(?:the\s+)?time(?:\s+now)?(?:\s+in\s+[\w\s]+)?'
        r'|what\s+time\s+is\s+it(?:\s+now)?(?:\s+in\s+[\w\s]+)?'
        r'|current\s+time(?:\s+in\s+[\w\s]+)?'
        r'|time\s+now(?:\s+in\s+[\w\s]+)?'
        r'|what\s+(?:is\s+)?(?:today\'s\s+)?date'
        r'|what\s+is\s+the\s+date\s+today'
        r'|what\s+day\s+is\s+today'
        r'|today\'s\s+date'
        r'|এখন\s*কয়টা\s*বাজে'
        r'|এখন\s*সময়\s*কত'
        r'|সময়\s*কত'
        r'|কয়টা\s*বাজে'
        r'|আজকে?\s*কত\s*তারিখ'
        r'|আজকে?\s*কী?\s*বার'
        r'|বর্তমান\s*সময়'
        r')\s*\??\s*$',
        re.IGNORECASE,
    )

    def __init__(self):
        try:
            self.web = WebSearch()
        except Exception as exc:
            logging.warning(f"[ClaudeClient] Primary WebSearch client not initialized ({exc})")
            self.web = None
        self.system_prompt = SYSTEM_PROMPT + "\n\n" + PROFILE_PROMPT
        self.messages = []

    @property
    def _provider_manager(self) -> ProviderManager:
        return ProviderManager.instance()

    def needs_web_search(self, prompt: str, is_live: bool = False) -> bool:
        if is_live:
            # In live voice mode, only trigger web search on explicit user request.
            # Casual conversational words ("আজ", "আজকে", "বর্তমান", "লাইভ", "today", "live")
            # must NEVER trigger a blocking 3-5 second web search during live audio turns!
            explicit_keywords = [
                "web search", "google search", "search web", "search online", "search the web",
                "search the internet", "অনলাইন সার্চ", "ওয়েব সার্চ", "অনুসন্ধান করুন", "ইন্টারনেটে খুঁজুন",
                "গুগলে সার্চ করো", "ইন্টারনেটে সার্চ করো"
            ]
            prompt_lower = prompt.lower()
            return any(k in prompt_lower for k in explicit_keywords)

        if self._PURE_TIME_PATTERN.search(prompt):
            return False
        return bool(self._WEB_PATTERN.search(prompt))

    def _get_dynamic_system_prompt(self, is_live: bool = False) -> str:
        from datetime import datetime, timezone, timedelta
        now_local = datetime.now().astimezone()
        local_str = now_local.strftime("%Y-%m-%d %I:%M:%S %p (%A)")
        tz_name = now_local.tzname() or "Local Time"

        bst_tz = timezone(timedelta(hours=6))
        now_bst = datetime.now(bst_tz)
        bst_str = now_bst.strftime("%Y-%m-%d %I:%M:%S %p (%A)")

        temporal_context = (
            f"\n\n# REAL-TIME SYSTEM CLOCK & TEMPORAL CONTEXT\n"
            f"- Local Machine System Time: {local_str} [{tz_name}]\n"
            f"- Bangladesh Standard Time (BST / UTC+6): {bst_str}\n\n"
            f"CRITICAL REAL-TIME CLOCK INSTRUCTIONS:\n"
            f"1. For questions regarding current time, date, day of week, or time in specific regions (e.g. Bangladesh), ALWAYS rely on the real-time system clock given above.\n"
            f"2. NEVER use static time values found in web search result snippets (which are historical cached snapshot text like '9:02 AM') for live time/date queries."
        )

        user_age_directive = ""
        try:
            from app.settings.settings_manager import SettingsManager
            cfg_schema = SettingsManager.instance().service.schema
            configured_age = getattr(cfg_schema.general, "user_age", 0)
            if 0 < configured_age <= 18:
                user_age_directive = (
                    f"\n\n# CONFIGURED USER AGE & ADDRESSING INSTRUCTION:\n"
                    f"- The user's configured age is {configured_age} years old (<= 18 years old).\n"
                    f"- MANDATORY BENGALI RULE: When communicating in Bengali, ALWAYS address the user affectionately and warmly as 'তুমি' (Tumi / তোমার / তোমাকে / করছ / করবে / বলো). NEVER address this user as 'আপনি'."
                )
            elif configured_age > 18:
                user_age_directive = (
                    f"\n\n# CONFIGURED USER AGE & ADDRESSING INSTRUCTION:\n"
                    f"- The user's configured age is {configured_age} years old (> 18 years old).\n"
                    f"- When communicating in Bengali, address the user respectfully as 'আপনি' (Apni)."
                )
        except Exception:
            pass

        live_voice_directive = ""
        if is_live:
            live_voice_directive = (
                "\n\n# REAL-TIME LIVE VOICE CONVERSATION DIRECTIVE:\n"
                "- You are speaking with the user in a real-time live voice conversation.\n"
                "- ADAPTIVE CONVERSATIONAL LENGTH: For simple chit-chat, greetings, or short questions, reply naturally in 1 to 2 spoken sentences. For intellectual, analytical, conceptual, or educational questions, provide a thoughtful, clear, and comprehensive explanation in 2 to 4 spoken sentences so the topic is explained thoroughly and well.\n"
                "- ZERO MARKDOWN RULE: Never output Markdown formatting, headings (###), bullet points, asterisks (**), or code blocks as your output will be directly read aloud by a Text-to-Speech audio engine. Speak in natural prose.\n"
                "- Reply in the exact same language spoken by the user (Bengali if spoken in Bengali, English if spoken in English)."
            )

        base_prompt = getattr(self, "system_prompt", SYSTEM_PROMPT + "\n\n" + PROFILE_PROMPT)
        return base_prompt + temporal_context + user_age_directive + live_voice_directive

    def _search_duckduckgo_fallback(self, query: str, max_results: int = 5) -> str:
        import html
        import httpx
        try:
            with httpx.Client(
                timeout=2.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                },
            ) as client:
                r = client.post("https://lite.duckduckgo.com/lite/", data={"q": query})
                if r.status_code != 200:
                    r = client.get("https://html.duckduckgo.com/html/", params={"q": query})

                titles = re.findall(r"class='result-link'[^>]*>(.*?)</a>", r.text, re.DOTALL)
                snippets = re.findall(r"class='result-snippet'[^>]*>(.*?)</td>", r.text, re.DOTALL)
                links = re.findall(r"class='link-text'[^>]*>(.*?)</span>", r.text, re.DOTALL)

                results = []
                for i in range(min(len(titles), len(snippets), max_results)):
                    t = html.unescape(re.sub(r"<.*?>", "", titles[i])).strip()
                    s = html.unescape(re.sub(r"<.*?>", "", snippets[i])).strip()
                    l = html.unescape(re.sub(r"<.*?>", "", links[i])).strip() if i < len(links) else ""
                    results.append(f"Result #{i+1}:\nTitle: {t}\nURL: {l}\nContent Snippet: {s}")

                return "\n\n".join(results)
        except Exception as exc:
            logging.warning(f"[ClaudeClient] DuckDuckGo fallback search exception: {exc}")
            return ""

    def _build_web_context(self, prompt: str) -> str:
        from datetime import datetime, timezone, timedelta
        now_local = datetime.now().astimezone()
        local_str = now_local.strftime("%Y-%m-%d %I:%M:%S %p (%A)")
        tz_name = now_local.tzname() or "Local Time"

        bst_tz = timezone(timedelta(hours=6))
        now_bst = datetime.now(bst_tz)
        bst_str = now_bst.strftime("%Y-%m-%d %I:%M:%S %p (%A)")

        snippets = []
        if self.web is not None:
            try:
                result = self.web.search(prompt, max_results=5)
                answer = result.get("answer")
                if answer and str(answer).strip():
                    snippets.append(f"AI Summary Answer: {answer.strip()}")

                results_list = result.get("results", [])
                for idx, item in enumerate(results_list, 1):
                    title = item.get("title", "").strip()
                    url = item.get("url", "").strip()
                    content = item.get("content", "").strip()
                    if content or title:
                        snippets.append(
                            f"Result #{idx}:\nTitle: {title}\nURL: {url}\nContent Snippet: {content}"
                        )
            except Exception as exc:
                logging.warning(f"[ClaudeClient] Primary Tavily web search failed ({exc})")

        if not snippets:
            fallback_res = self._search_duckduckgo_fallback(prompt)
            if fallback_res:
                snippets.append(fallback_res)
            else:
                snippets.append("No direct web snippets could be retrieved due to a temporary network issue.")

        web_data_block = "\n\n---\n\n".join(snippets)

        return f"""Current System Local Time: {local_str} [{tz_name}] | Bangladesh Standard Time (BST): {bst_str}

IMPORTANT INSTRUCTION FOR AI ASSISTANT:
Real-time web search results have been fetched automatically for the user's question below.
Do NOT say "I cannot access live data" or "I don't have real-time information".
Use the real-time search snippets for general news, weather, prices, sports, or live events.
However, FOR CURRENT TIME / DATE / CLOCK QUERIES, ALWAYS USE THE LIVE SYSTEM CLOCK ABOVE instead of static web search snippets.

==================== REAL-TIME WEB SEARCH DATA ====================
{web_data_block}
====================================================================

USER QUESTION:
{prompt}
"""

    def _resolve_provider_id(self, model: str) -> tuple[str, str]:
        """Map model slug to target provider_id and normalized model name."""
        model_str = (model or self.DEFAULT_MODEL).strip()
        model_str_lower = model_str.lower()

        if model_str_lower.startswith("google/") or "gemini" in model_str_lower:
            return "google_ai_studio", model_str
        elif (
            model_str_lower.startswith("groq/")
            or model_str_lower.startswith("groq-")
            or model_str_lower in ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b")
        ):
            return "groq", model_str
        elif (
            model_str_lower.startswith("cerebras/")
            or model_str_lower.startswith("cerebras-")
            or model_str_lower in ("qwen-3.8-27b", "gpt-oss-120b")
        ):
            return "cerebras", model_str
        elif model_str_lower.startswith("ollama/") or model_str_lower.startswith("ollama-"):
            return "ollama", model_str
        elif (
            model_str_lower.startswith("plugsky/")
            or model_str_lower.startswith("plugsky-")
            or model_str_lower.startswith("plugsky")
            or "plugsky" in model_str_lower
        ):
            return "plugsky", model_str
        elif model_str_lower.startswith("claude-") or model_str_lower.startswith("anthropic/"):
            return "anthropic", model_str
        else:
            return "openrouter", model_str

    def ask(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        history: Sequence[dict[str, Any]] | None = None,
        provider_id: str | None = None,
        is_live: bool = False,
    ) -> str:
        full_text = []
        for chunk in self.ask_stream(prompt, model=model, max_tokens=max_tokens, history=history, provider_id=provider_id, is_live=is_live):
            full_text.append(chunk)
        return "".join(full_text)

    def ask_stream(
        self,
        prompt: str | list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 2048,
        history: Sequence[dict[str, Any]] | None = None,
        provider_id: str | None = None,
        is_live: bool = False,
    ):
        # Support mock client injected via test helper (_client_with)
        if getattr(self, "client", None) is not None:
            yield from self._stream_anthropic_direct(getattr(self, "client"), model or self.DEFAULT_MODEL, prompt, max_tokens, history)
            return

        final_prompt = prompt
        if isinstance(prompt, str) and self.needs_web_search(prompt, is_live=is_live):
            final_prompt = self._build_web_context(prompt)

        raw_history = self._request_messages(history)
        msg_contents = []
        for item in raw_history:
            role = item.get("role", "user")
            content = item.get("content", "")
            msg_contents.append(MessageContent(role=role, content=content))

        if isinstance(final_prompt, str) and final_prompt.strip():
            if not (msg_contents and msg_contents[-1].role == "user" and isinstance(msg_contents[-1].content, str) and msg_contents[-1].content.strip() == final_prompt.strip()):
                msg_contents.append(MessageContent(role="user", content=final_prompt))
        elif isinstance(final_prompt, list):
            msg_contents.append(MessageContent(role="user", content=final_prompt))

        target_model = model or self.DEFAULT_MODEL
        if provider_id and str(provider_id).strip():
            resolved_provider = str(provider_id).strip()
            norm_model = target_model
        else:
            resolved_provider, norm_model = self._resolve_provider_id(target_model)

        req = ChatRequest(
            messages=msg_contents,
            model=norm_model,
            system_prompt=self._get_dynamic_system_prompt(is_live=is_live),
            max_tokens=max_tokens,
            stream=True,
        )

        full_text = []
        accumulated_reasoning = []
        try:
            for stream_chunk in self._provider_manager.chat_stream(req, provider_id=resolved_provider):
                if stream_chunk.reasoning_delta:
                    accumulated_reasoning.append(stream_chunk.reasoning_delta)
                if stream_chunk.delta:
                    full_text.append(stream_chunk.delta)
                    yield stream_chunk.delta

            # If the model ONLY emitted reasoning tokens and zero normal content, yield reasoning as fallback
            if not full_text and accumulated_reasoning:
                fallback_reply = "".join(accumulated_reasoning)
                full_text.append(fallback_reply)
                yield fallback_reply
        except Exception as exc:
            raise RuntimeError(f"Provider Execution Error ({target_model}): {exc}") from exc

        answer = "".join(full_text)
        if history is None:
            if not hasattr(self, "messages"):
                self.messages = []
            self.messages = [m.__dict__ for m in msg_contents]
            self.messages.append({"role": "assistant", "content": answer})

    def _stream_anthropic_direct(self, client, model: str, prompt, max_tokens: int, history):
        request_messages = self._request_messages(history)
        if isinstance(prompt, str) and prompt.strip():
            if not (request_messages and request_messages[-1].get("role") == "user" and request_messages[-1].get("content", "").strip() == prompt.strip()):
                request_messages.append({"role": "user", "content": prompt})

        full_text = []
        try:
            with client.messages.stream(
                model=model,
                system=self._get_dynamic_system_prompt(),
                max_tokens=max_tokens,
                messages=request_messages,
            ) as stream:
                text_generator = getattr(stream, "text_stream", [])
                for text in text_generator:
                    full_text.append(text)
                    yield text
        except Exception as exc:
            raise RuntimeError("connection failed") from exc

        answer = "".join(full_text)
        if history is None:
            if not hasattr(self, "messages"):
                self.messages = []
            self.messages = request_messages
            self.messages.append({"role": "assistant", "content": answer})

    def _request_messages(
        self, history: Sequence[dict[str, Any]] | None
    ) -> list[dict[str, Any]]:
        source = getattr(self, "messages", []) if history is None else history
        return [dict(message) for message in source]

    def history(self) -> list[dict[str, Any]]:
        return getattr(self, "messages", [])
