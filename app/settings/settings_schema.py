"""Strongly-typed dataclasses for all settings categories and provider configurations."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any



@dataclass
class ProviderConfig:
    """Configuration for a single AI service provider."""
    name: str = ""
    enabled: bool = False
    api_key: str = ""
    base_url: str = ""
    status: str = "not_configured"  # options: not_configured, active, error
    priority: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderConfig:
        return cls(
            name=str(data.get("name", "")),
            enabled=bool(data.get("enabled", False)),
            api_key=str(data.get("api_key", "")),
            base_url=str(data.get("base_url", "")),
            status=str(data.get("status", "not_configured")),
            priority=int(data.get("priority", 1)),
        )


@dataclass
class ModelConfig:
    """Mapping of AI task roles to specific model identifiers."""
    chat_model: str = "deepseek/deepseek-chat"
    coding_model: str = "deepseek/deepseek-chat"
    reasoning_model: str = "deepseek/deepseek-r1"
    vision_model: str = "openai/gpt-4o"
    voice_model: str = "eleven_v3"
    image_model: str = "openai/dall-e-3"
    fallback_model: str = "deepseek/deepseek-chat"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelConfig:
        return cls(
            chat_model=str(data.get("chat_model", "deepseek/deepseek-chat")),
            coding_model=str(data.get("coding_model", "deepseek/deepseek-chat")),
            reasoning_model=str(data.get("reasoning_model", "deepseek/deepseek-r1")),
            vision_model=str(data.get("vision_model", "openai/gpt-4o")),
            voice_model=str(data.get("voice_model", "eleven_v3")),
            image_model=str(data.get("image_model", "openai/dall-e-3")),
            fallback_model=str(data.get("fallback_model", "deepseek/deepseek-chat")),
        )


@dataclass
class GeneralSettings:
    language: str = "en"
    auto_startup: bool = False
    notifications_enabled: bool = True
    user_age: int = 0  # 0 = auto-detect / not set

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeneralSettings:
        return cls(
            language=str(data.get("language", "en")),
            auto_startup=bool(data.get("auto_startup", False)),
            notifications_enabled=bool(data.get("notifications_enabled", True)),
            user_age=int(data.get("user_age", 0)),
        )


@dataclass
class AppearanceSettings:
    theme: str = "light"
    font_family: str = "Segoe UI"
    font_scale: float = 1.0
    message_density: str = "comfortable"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppearanceSettings:
        return cls(
            theme=str(data.get("theme", "light")),
            font_family=str(data.get("font_family", "Segoe UI")),
            font_scale=float(data.get("font_scale", 1.0)),
            message_density=str(data.get("message_density", "comfortable")),
        )


@dataclass
class VoiceSettingsSchema:
    stt_provider_id: str = "google_stt"
    tts_provider_id: str = "edge_neural_tts"
    voice_id: str = "bn-BD-NabanitaNeural"
    custom_voices: list[dict[str, Any]] = field(default_factory=list)
    auto_send: bool = True
    voice_response: bool = True
    silence_timeout_ms: int = 1300
    vad_threshold: float = 0.020  # Aligned with VoiceSettings default
    language: str = "bn"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceSettingsSchema:
        return cls(
            stt_provider_id=str(data.get("stt_provider_id", "google_stt")),
            tts_provider_id=str(data.get("tts_provider_id", "edge_neural_tts")),
            voice_id=str(data.get("voice_id", "bn-BD-NabanitaNeural")),
            custom_voices=list(data.get("custom_voices", [])),
            auto_send=bool(data.get("auto_send", True)),
            voice_response=bool(data.get("voice_response", True)),
            silence_timeout_ms=int(data.get("silence_timeout_ms", 1300)),
            vad_threshold=float(data.get("vad_threshold", 0.008)),
            language=str(data.get("language", "bn")),
        )


@dataclass
class ChatSettingsSchema:
    system_persona: str = "default"
    custom_system_prompt: str = ""
    attach_user_profile: bool = True
    max_history_turns: int = 20
    temperature: float = 0.7
    max_tokens: int = 2048

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatSettingsSchema:
        return cls(
            system_persona=str(data.get("system_persona", "default")),
            custom_system_prompt=str(data.get("custom_system_prompt", "")),
            attach_user_profile=bool(data.get("attach_user_profile", True)),
            max_history_turns=int(data.get("max_history_turns", 20)),
            temperature=float(data.get("temperature", 0.7)),
            max_tokens=int(data.get("max_tokens", 2048)),
        )


@dataclass
class ExportSettingsSchema:
    default_format: str = "pdf"
    include_timestamps: bool = True
    include_attachments: bool = True
    paper_size: str = "A4"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportSettingsSchema:
        return cls(
            default_format=str(data.get("default_format", "pdf")),
            include_timestamps=bool(data.get("include_timestamps", True)),
            include_attachments=bool(data.get("include_attachments", True)),
            paper_size=str(data.get("paper_size", "A4")),
        )


@dataclass
class AdvancedSettingsSchema:
    log_level: str = "INFO"
    auto_sweep_orphans: bool = True
    cache_limit_mb: int = 500

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdvancedSettingsSchema:
        return cls(
            log_level=str(data.get("log_level", "INFO")),
            auto_sweep_orphans=bool(data.get("auto_sweep_orphans", True)),
            cache_limit_mb=int(data.get("cache_limit_mb", 500)),
        )


@dataclass
class AboutSettingsSchema:
    app_name: str = "Jakariya AI Studio"
    version: str = "1.0.0"
    creator: str = "Md. Jakariya Sheikh"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AboutSettingsSchema:
        return cls(
            app_name=str(data.get("app_name", "Jakariya AI Studio")),
            version=str(data.get("version", "1.0.0")),
            creator=str(data.get("creator", "Md. Jakariya Sheikh")),
        )


@dataclass
class AppSettingsSchema:
    """Master configuration container for all application setting sections."""
    schema_version: str = "1.0.0"
    app_version: str = "1.0.0"
    general: GeneralSettings = field(default_factory=GeneralSettings)
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    models: ModelConfig = field(default_factory=ModelConfig)
    voice: VoiceSettingsSchema = field(default_factory=VoiceSettingsSchema)
    chat: ChatSettingsSchema = field(default_factory=ChatSettingsSchema)
    export: ExportSettingsSchema = field(default_factory=ExportSettingsSchema)
    advanced: AdvancedSettingsSchema = field(default_factory=AdvancedSettingsSchema)
    about: AboutSettingsSchema = field(default_factory=AboutSettingsSchema)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppSettingsSchema:
        providers_data = data.get("providers", {})
        providers_dict = {}
        for p_id, p_conf in providers_data.items():
            if isinstance(p_conf, dict):
                providers_dict[p_id] = ProviderConfig.from_dict(p_conf)

        return cls(
            schema_version=str(data.get("schema_version", "1.0.0")),
            app_version=str(data.get("app_version", "1.0.0")),
            general=GeneralSettings.from_dict(data.get("general", {})),
            appearance=AppearanceSettings.from_dict(data.get("appearance", {})),
            providers=providers_dict,
            models=ModelConfig.from_dict(data.get("models", {})),
            voice=VoiceSettingsSchema.from_dict(data.get("voice", {})),
            chat=ChatSettingsSchema.from_dict(data.get("chat", {})),
            export=ExportSettingsSchema.from_dict(data.get("export", {})),
            advanced=AdvancedSettingsSchema.from_dict(data.get("advanced", {})),
            about=AboutSettingsSchema.from_dict(data.get("about", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        res = {
            "schema_version": self.schema_version,
            "app_version": self.app_version,
            "general": asdict(self.general),
            "appearance": asdict(self.appearance),
            "providers": {k: asdict(v) for k, v in self.providers.items()},
            "models": asdict(self.models),
            "voice": asdict(self.voice),
            "chat": asdict(self.chat),
            "export": asdict(self.export),
            "advanced": asdict(self.advanced),
            "about": asdict(self.about),
        }
        return res
