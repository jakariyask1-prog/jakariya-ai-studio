"""Tests for FishAudioTTS provider and environment fallback."""

import os
from unittest.mock import patch
from app.voice.business_logic.tts.fish_audio_tts import FishAudioTTS


def test_fish_audio_tts_env_fallback():
    """Verify FishAudioTTS detects FISH_AUDIO_API_KEY from environment."""
    with patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "test_fish_key_12345"}):
        with patch("app.settings.settings_manager.SettingsManager.instance") as mock_mgr:
            mock_mgr.return_value.service.get_api_key.return_value = ""
            tts = FishAudioTTS()
            assert tts._get_api_key() == "test_fish_key_12345"
            assert tts.is_available() is True


def test_fish_audio_tts_no_key():
    """Verify FishAudioTTS reports unavailable when key is empty."""
    with patch.dict(os.environ, {"FISH_AUDIO_API_KEY": ""}):
        with patch("app.settings.settings_manager.SettingsManager.instance") as mock_mgr:
            mock_mgr.return_value.service.get_api_key.return_value = ""
            tts = FishAudioTTS()
            assert tts._get_api_key() == ""
            assert tts.is_available() is False
