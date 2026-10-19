"""Voice presets and custom voice management for text-to-speech providers.

Provides curated preset voices for each TTS engine (Edge Neural, Cartesia AI,
ElevenLabs, Fish Audio, Google TTS) and utilities for merging user-defined
custom / cloned voice IDs.
"""

from __future__ import annotations

from typing import Any

# Curated Presets by TTS provider_id
# Format: (Display Label, Voice ID / speaker string)
VOICE_PRESETS: dict[str, list[tuple[str, str]]] = {
    "edge_neural_tts": [
        ("🇧🇩 Nabanita (Bangla - Female / বাংলাদেশ - Recommended)", "bn-BD-NabanitaNeural"),
        ("🇧🇩 Pradeep (Bangla - Male / বাংলাদেশ)", "bn-BD-PradeepNeural"),
        ("🇮🇳 Tanishaa (Bangla - Female / ভারত)", "bn-IN-TanishaaNeural"),
        ("🇮🇳 Bashkar (Bangla - Male / ভারত)", "bn-IN-BashkarNeural"),
        ("🇺🇸 Jenny (English US - Female / Natural & Warm)", "en-US-JennyNeural"),
        ("🇺🇸 Guy (English US - Male / Confident)", "en-US-GuyNeural"),
        ("🇺🇸 Aria (English US - Female / Expressive)", "en-US-AriaNeural"),
        ("🇬🇧 Sonia (English UK - Female / Elegant)", "en-GB-SoniaNeural"),
        ("🇬🇧 Ryan (English UK - Male / Professional)", "en-GB-RyanNeural"),
        ("🇮🇳 Swara (Hindi - Female / ভারত)", "hi-IN-SwaraNeural"),
        ("🇮🇳 Madhur (Hindi - Male / ভারত)", "hi-IN-MadhurNeural"),
    ],
    "cartesia": [
        ("⭐ Personal Cloned Voice - Bangla (Cartesia AI)", "2c8d7dfb-ca84-4888-9600-8d8c54022dba"),
        ("⭐ Personal Cloned Voice - English (Cartesia AI)", "e8299d96-b115-4ed1-80aa-2696eb5335ca"),
        ("🇬🇧 British Conversational Lady (Cartesia Sonic)", "694f9389-aac1-45b6-b726-9d9369183238"),
        ("🇺🇸 Greg - Warm Supporter (Cartesia Sonic)", "a0e99841-438c-4a64-b679-ae501e7d6091"),
        ("🇺🇸 Linda - Conversational Guide (Cartesia Sonic)", "829ccd10-f8b3-43cd-b8a0-4aeaa81f3b30"),
        ("🇺🇸 Riley - Chill Friend (Cartesia Sonic)", "21b81c14-f85b-436d-aff5-43f2e788ecf8"),
        ("🇺🇸 Troy - Confident (Cartesia Sonic)", "726d5ae5-055f-4c3d-8355-d9677de68937"),
        ("🌐 Kai - Commercial Multilingual (Cartesia Sonic)", "eda5bbff-1ff1-4886-8ef1-4e69a77640a0"),
    ],
    "elevenlabs": [
        ("👩 Sarah (Warm & Expressive - Best for Bangla & English)", "EXAVITQu4vr4xnSDxMaL"),
        ("👨 Adam (Deep, Confident & Clear - Best for English & Bangla)", "pNInz6obpgDQGcFmaJgB"),
        ("👩 Rachel (Calm, Professional & Natural)", "21m00Tcm4TlvDq8ikWAM"),
        ("👨 George (Warm & Resonant Storyteller)", "JBFqnCBsd6RMkjVDRZzb"),
        ("👩 Alice (Clear & Articulate)", "Xb7hH8MSUJpSbSDYk0k2"),
        ("👩 Domi (Energetic & Dynamic)", "AZnzlk1XvdvUeBnXmlld"),
        ("👨 Arnold (Crisp & Authoritative)", "VR6AewLTigWG4xSOukaG"),
        ("👩 Elli (Emotional & Gentle)", "MF3mGyEYCl7XYWbV9V6O"),
    ],
    "fish_audio": [
        ("🐟 Fish Audio Default Model (s2.1-pro)", "default"),
    ],
    "google_tts": [
        ("🌐 Google gTTS Auto Voice (Basic)", "google_default"),
    ],
}

DEFAULT_VOICES_BY_PROVIDER: dict[str, str] = {
    "edge_neural_tts": "bn-BD-NabanitaNeural",
    "cartesia": "2c8d7dfb-ca84-4888-9600-8d8c54022dba",
    "elevenlabs": "EXAVITQu4vr4xnSDxMaL",
    "fish_audio": "default",
    "google_tts": "google_default",
}


def get_default_voice_for_provider(provider_id: str) -> str:
    """Return the default voice ID for the given TTS provider."""
    pid = (provider_id or "").strip()
    return DEFAULT_VOICES_BY_PROVIDER.get(pid, "bn-BD-NabanitaNeural")


def get_presets_for_provider(provider_id: str) -> list[tuple[str, str]]:
    """Return the list of curated preset voices for a provider."""
    pid = (provider_id or "").strip()
    return list(VOICE_PRESETS.get(pid, []))


def get_voices_for_provider(
    provider_id: str,
    custom_voices: list[dict[str, Any]] | None = None,
) -> list[tuple[str, str]]:
    """Return presets plus user-added custom voices matching the provider."""
    pid = (provider_id or "").strip()
    result: list[tuple[str, str]] = get_presets_for_provider(pid)

    if custom_voices:
        for cv in custom_voices:
            if not isinstance(cv, dict):
                continue
            c_id = str(cv.get("id", "")).strip()
            c_name = str(cv.get("name", "")).strip() or c_id
            c_prov = str(cv.get("provider_id", "")).strip()

            # Include if matching this provider or if generic (no provider specified)
            if c_id and (not c_prov or c_prov == pid):
                # Avoid duplicate IDs
                if not any(existing_id == c_id for _, existing_id in result):
                    result.append((f"✨ [Custom] {c_name}", c_id))

    return result


def get_voice_label(
    provider_id: str,
    voice_id: str,
    custom_voices: list[dict[str, Any]] | None = None,
) -> str:
    """Return a human-friendly label for a given voice ID."""
    all_voices = get_voices_for_provider(provider_id, custom_voices)
    for label, v_id in all_voices:
        if v_id == voice_id:
            return label
    return f"Voice ({voice_id})"
