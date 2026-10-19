"""AI Models task mapping page widget for assigning independent models to task roles."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.settings.settings_schema import ModelConfig
from app.settings.provider_registry import ProviderRegistry


class ModelsPage(QWidget):
    """AI Models settings UI page (Chat, Coding, Reasoning, Vision, Voice, Image, Fallback)."""

    setting_changed = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._combos: dict[str, QComboBox] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # Title
        title_label = QLabel("AI Model Task Role Mapping")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(title_label)

        desc_label = QLabel("Assign models independently to task roles. Changing providers or models requires no application logic changes.")
        desc_label.setStyleSheet("color: #888888; font-size: 12px;")
        main_layout.addWidget(desc_label)

        # Scroll Area for Task Mapping Groups
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        scroll_layout = QVBoxLayout(container)
        scroll_layout.setContentsMargins(0, 5, 10, 5)
        scroll_layout.setSpacing(15)

        # Fetch dynamic model list from ProviderRegistry
        registry_models = ProviderRegistry.get_all_models()

        # Task Role Specs (role_key, display_name, description, default_presets)
        task_specs = [
            (
                "chat_model",
                "💬 General Chat Model",
                "Default conversational intelligence model for text interactions.",
                ["google/gemini-2.0-flash", "deepseek/deepseek-chat", "openai/gpt-4o-mini", "plugsky-lite"],
            ),
            (
                "coding_model",
                "💻 Coding & Software Architecture Model",
                "Specialized model for code generation, debugging, and technical specs.",
                [
                    "anthropic/claude-3.7-sonnet",
                    "anthropic/claude-3.5-sonnet",
                    "google/gemini-2.5-pro",
                    "google/gemini-2.0-flash",
                    "deepseek/deepseek-chat",
                    "qwen/qwen-2.5-coder-32b-instruct",
                    "llama-3.3-70b-versatile",
                    "codestral-latest",
                    "plugsky-lite",
                ],
            ),
            (
                "reasoning_model",
                "🧠 Complex Reasoning & Scientific Model",
                "Deep reasoning model for math, research, logic, and multi-step analytical problems.",
                [
                    "deepseek/deepseek-r1",
                    "google/gemini-2.0-flash-thinking-exp",
                    "google/gemini-2.5-pro",
                    "deepseek-r1-distill-llama-70b",
                    "plugsky-reasoning",
                ],
            ),
            (
                "vision_model",
                "👁️ Vision & Multimodal Model",
                "Model used for analyzing uploaded images, screenshots, and visual documents.",
                ["openai/gpt-4o", "google/gemini-3.6-flash", "meta-llama/llama-3.2-11b-vision-instruct"],
            ),
            (
                "voice_model",
                "🎙️ Voice Speech Engine Model",
                "Primary TTS voice model engine for audio synthesis.",
                ["edge_neural_tts", "cartesia", "elevenlabs", "fish_audio", "gtts"],
            ),
            (
                "image_model",
                "🎨 Image Generation Model",
                "Text-to-Image generation model engine.",
                ["openai/dall-e-3", "stability-ai/sdxl"],
            ),
            (
                "fallback_model",
                "🛡️ Backup / Fallback Model",
                "Emergency backup model when primary provider endpoints return rate limits or errors.",
                ["plugsky-lite", "google/gemini-3.6-flash", "deepseek/deepseek-chat"],
            ),
        ]

        for role_key, name, desc, defaults in task_specs:
            group = QGroupBox(name)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(15, 12, 15, 12)
            group_layout.setSpacing(8)

            desc_sub = QLabel(desc)
            desc_sub.setStyleSheet("color: #9CA3AF; font-size: 11px;")
            group_layout.addWidget(desc_sub)

            combo = QComboBox()
            combo.setEditable(True)

            # Combine registry models and defaults uniquely
            combined_models = list(dict.fromkeys(defaults + registry_models))
            for model_id in combined_models:
                combo.addItem(model_id)

            combo.currentIndexChanged.connect(self._on_changed)
            combo.currentTextChanged.connect(self._on_changed)
            self._combos[role_key] = combo

            group_layout.addWidget(combo)
            scroll_layout.addWidget(group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _on_changed(self) -> None:
        self.setting_changed.emit("models", self.get_settings())

    def load_settings(self, settings: ModelConfig) -> None:
        """Populate model combos from ModelConfig object."""
        self.blockSignals(True)
        for role_key, combo in self._combos.items():
            model_val = getattr(settings, role_key, "deepseek/deepseek-chat")
            idx = combo.findText(model_val)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(model_val)
        self.blockSignals(False)

    def get_settings(self) -> ModelConfig:
        """Return ModelConfig constructed from UI values."""
        kwargs = {}
        for role_key, combo in self._combos.items():
            kwargs[role_key] = combo.currentText().strip()
        return ModelConfig(**kwargs)
