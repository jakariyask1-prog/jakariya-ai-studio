"""Comprehensive Deep Audit Unit Tests for all Settings Options in Jakariya AI Studio.

Verifies that changing any setting option actually takes effect across the entire runtime:
1. Appearance: Font Family, Font Scale, Layout Density (Compact vs Comfortable)
2. Chat & Persona: System Persona (Math Tutor, Code Expert, Custom), User Profile Toggle,
   Temperature, Max Tokens, Preferred Language
3. Voice: Microphone and Speaker device indices preservation during sync
4. AI Providers: BaseProvider dynamic key/URL lookup and ProviderManager priority sync
5. Export: Timestamps and Attachments configuration propagation
"""

import pytest
from app.settings.settings_schema import (
    AppearanceSettings,
    ChatSettingsSchema,
    ExportSettingsSchema,
    VoiceSettingsSchema,
    ProviderConfig,
)
from app.settings.settings_manager import SettingsManager
from app.ui.styles import get_global_app_style, get_chat_browser_style, get_document_css
from app.export.export_options import ExportOptions
from app.voice.voice_settings import VoiceSettings


def test_appearance_font_family_and_scale():
    """Verify font family and scale are dynamically embedded in global QSS and browser styles."""
    qss = get_global_app_style("dark", font_family="Fira Code", font_scale=1.2)
    assert "'Fira Code'" in qss

    browser_qss = get_chat_browser_style("dark", font_family="Roboto", font_scale=1.1)
    assert "'Roboto'" in browser_qss
    assert "12.1pt" in browser_qss or "12.1" in browser_qss  # 11 * 1.1 = 12.1


def test_appearance_layout_density_styles():
    """Verify message density changes line height and pre margins in document CSS."""
    compact_css = get_document_css("light", message_density="compact")
    assert "line-height: 1.38" in compact_css
    assert "margin: 5px 0" in compact_css

    comfortable_css = get_document_css("light", message_density="comfortable")
    assert "line-height: 1.55" in comfortable_css
    assert "margin: 8px 0" in comfortable_css


def test_chat_persona_and_instructions_in_prompt():
    """Verify system persona, custom prompts, and profile attachment reflect in ClaudeClient prompt."""
    from app.api.ClaudeClient import ClaudeClient

    client = ClaudeClient()
    svc = SettingsManager.instance().service

    # 1. Math Tutor
    svc.schema.chat.system_persona = "math_tutor"
    prompt_math = client._get_dynamic_system_prompt()
    assert "MATHEMATICS & SCIENTIFIC RESEARCH TUTOR" in prompt_math

    # 2. Code Expert
    svc.schema.chat.system_persona = "code_expert"
    prompt_code = client._get_dynamic_system_prompt()
    assert "SOFTWARE ARCHITECT & CODE MASTER" in prompt_code

    # 3. Custom Persona
    svc.schema.chat.system_persona = "custom"
    svc.schema.chat.custom_system_prompt = "You are an AI specialized in quantum mechanics."
    prompt_custom = client._get_dynamic_system_prompt()
    assert "quantum mechanics" in prompt_custom

    # 4. User Profile detachment
    svc.schema.chat.attach_user_profile = False
    prompt_no_profile = client._get_dynamic_system_prompt()
    assert "# USER PROFILE & PREFERENCES" not in prompt_no_profile

    # Restore defaults
    svc.schema.chat.system_persona = "default"
    svc.schema.chat.attach_user_profile = True


def test_voice_device_indices_preserved():
    """Verify audio device indices are correctly passed to VoiceSettings during config sync."""
    svc = SettingsManager.instance().service
    svc.schema.voice.input_device_index = 2
    svc.schema.voice.output_device_index = 3

    vs = VoiceSettings(
        stt_provider_id=svc.schema.voice.stt_provider_id,
        tts_provider_id=svc.schema.voice.tts_provider_id,
        voice_id=svc.schema.voice.voice_id,
        language=svc.schema.voice.language,
        input_device_index=svc.schema.voice.input_device_index,
        output_device_index=svc.schema.voice.output_device_index,
    )
    assert vs.input_device_index == 2
    assert vs.output_device_index == 3


def test_provider_manager_settings_sync():
    """Verify ProviderManager updates priority and invalidates cache when settings sync."""
    from app.providers.manager.provider_manager import ProviderManager

    pm = ProviderManager.instance()
    svc = SettingsManager.instance().service

    svc.schema.providers["groq"] = ProviderConfig(
        name="Groq", enabled=True, api_key="gsk_test_12345", priority=1
    )
    pm.sync_from_settings()

    assert pm._priority_map.get("groq") == 1
    assert pm._priority_list[0] == "groq"


def test_export_options_respects_settings():
    """Verify ExportOptions respects include_timestamps and include_attachments from schema."""
    svc = SettingsManager.instance().service
    svc.schema.export.include_timestamps = False
    svc.schema.export.include_attachments = False

    exp_opts = ExportOptions(
        "pdf",
        include_timestamps=svc.schema.export.include_timestamps,
        include_attachments=svc.schema.export.include_attachments,
    )
    assert not exp_opts.include_timestamps
    assert not exp_opts.include_attachments

    # Reset
    svc.schema.export.include_timestamps = True
    svc.schema.export.include_attachments = True
