"""Tests for ElevenLabsTTS and ElevenLabsSTT providers."""

import os
from unittest.mock import patch, MagicMock
from app.voice.business_logic.tts.elevenlabs_tts import ElevenLabsTTS
from app.voice.business_logic.stt.elevenlabs_stt import ElevenLabsSTT


def test_elevenlabs_tts_env_fallback():
    """Verify ElevenLabsTTS detects ELEVENLABS_API_KEY from environment."""
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test_eleven_key_12345"}):
        with patch("app.settings.settings_manager.SettingsManager.instance") as mock_mgr:
            mock_mgr.return_value.service.get_api_key.return_value = ""
            tts = ElevenLabsTTS()
            assert tts._get_api_key() == "test_eleven_key_12345"
            assert tts.is_available() is True
            assert tts.provider_id == "elevenlabs"


def test_elevenlabs_tts_no_key():
    """Verify ElevenLabsTTS reports unavailable when key is empty."""
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": ""}):
        with patch("app.settings.settings_manager.SettingsManager.instance") as mock_mgr:
            mock_mgr.return_value.service.get_api_key.return_value = ""
            tts = ElevenLabsTTS()
            assert tts._get_api_key() == ""
            assert tts.is_available() is False


def test_elevenlabs_stt_env_fallback():
    """Verify ElevenLabsSTT detects ELEVENLABS_API_KEY and checks availability."""
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test_eleven_key_12345"}):
        with patch("app.settings.settings_manager.SettingsManager.instance") as mock_mgr:
            mock_mgr.return_value.service.get_api_key.return_value = ""
            stt = ElevenLabsSTT()
            assert stt._get_api_key() == "test_eleven_key_12345"
            assert stt.is_available() is True
            assert stt.provider_id == "elevenlabs_stt"


def test_elevenlabs_stt_transcribe_mock():
    """Verify ElevenLabsSTT transcription request formatting."""
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test_eleven_key_12345"}):
        stt = ElevenLabsSTT()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "Hello world from Scribe"}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = stt.transcribe(b"fake_wav_audio_bytes", "en-US")
            assert result == "Hello world from Scribe"
            assert mock_post.called
            args, kwargs = mock_post.call_args
            assert "https://api.elevenlabs.io/v1/speech-to-text" in args[0]
            assert kwargs["headers"]["xi-api-key"] == "test_eleven_key_12345"
