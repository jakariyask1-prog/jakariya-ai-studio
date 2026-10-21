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
        main_layout.setContentsMargins(16, 12, 16, 8)
        main_layout.setSpacing(10)

        # Title & Subtitle Banner
        self.title_label = QLabel("🤖 AI Model Task Role Mapping")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        main_layout.addWidget(self.title_label)

        desc_label = QLabel("Assign AI models independently to specific tasks. All changes dynamically propagate across the entire studio without restarting.")
        desc_label.setProperty("subtext", "true")
        desc_label.setWordWrap(True)
        main_layout.addWidget(desc_label)

        # Scroll Area for Task Mapping Groups
        scroll = QScrollArea()
        scroll.setObjectName("modelsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea#modelsScrollArea, QScrollArea#modelsScrollArea > QWidget > QWidget { background: transparent; border: none; }")

        container = QWidget()
        container.setObjectName("modelsContainer")
        container.setStyleSheet("QWidget#modelsContainer { background: transparent; border: none; }")
        scroll_layout = QVBoxLayout(container)
        scroll_layout.setContentsMargins(0, 4, 10, 4)
        scroll_layout.setSpacing(10)

        # Fetch dynamic model list from ProviderRegistry
        registry_models = ProviderRegistry.get_all_models()

        # Task Role Specs (role_key, display_name, description, default_presets)
        task_specs = [
            (
                "chat_model",
                "💬 General Chat Model",
                "Default conversational intelligence model for text interactions.",
                ["google/gemini-3.8-flash", "google/gemini-3.6-flash", "deepseek/deepseek-chat", "openai/gpt-4o-mini", "plugsky-lite"],
            ),
            (
                "coding_model",
                "💻 Coding & Software Architecture Model",
                "Specialized model for code generation, debugging, and technical specs.",
                [
                    "qwen/qwen-2.5-coder-32b-instruct",
                    "deepseek/deepseek-chat",
                    "google/gemini-3.8-flash",
                    "google/gemini-3.6-flash",
                    "codestral-latest",
                    "openai/gpt-oss-120b",
                    "plugsky-lite",
                ],
            ),
            (
                "reasoning_model",
                "🧠 Complex Reasoning & Scientific Model",
                "Deep reasoning model for math, research, logic, and multi-step analytical problems.",
                [
                    "google/gemini-3.7-flash",
                    "openai/gpt-oss-120b",
                    "google/gemini-pro-latest",
                    "deepseek/deepseek-chat",
                    "openai/gpt-4o-mini",
                ],
            ),
            (
                "vision_model",
                "👁️ Vision & Multimodal Model",
                "Model used for analyzing uploaded images, screenshots, and visual documents.",
                ["google/gemini-3.8-flash", "google/gemini-3.6-flash", "openai/gpt-4o"],
            ),
            (
                "voice_model",
                "🎙️ Voice Speech Engine Model",
                "Primary TTS voice model engine for audio synthesis.",
                ["cartesia", "edge_neural_tts", "elevenlabs", "fish_audio", "gtts"],
            ),
            (
                "image_model",
                "🎨 Image Generation Model",
                "Text-to-Image generation model engine.",
                ["google/gemini-3.5-flash", "openai/dall-e-3", "stability-ai/sdxl"],
            ),
            (
                "fallback_model",
                "🛡️ Backup / Fallback Model",
                "Emergency backup model when primary provider endpoints return rate limits or errors.",
                ["google/gemini-3.6-flash", "plugsky-lite", "deepseek/deepseek-chat"],
            ),
        ]

        for role_key, name, desc, defaults in task_specs:
            group = QGroupBox(name)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(14, 10, 14, 10)
            group_layout.setSpacing(6)

            desc_sub = QLabel(desc)
            desc_sub.setProperty("subtext", "true")
            group_layout.addWidget(desc_sub)

            combo = QComboBox()
            combo.setEditable(True)
            if combo.lineEdit():
                combo.lineEdit().setPlaceholderText("Select or enter model ID...")

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

    def apply_theme(self, theme_name: str) -> None:
        """Propagate active theme to models page title and controls."""
        from app.ui.styles import get_theme_palette, apply_combobox_theme
        p = get_theme_palette(theme_name)
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {p['input_text']};")
        for combo in self._combos.values():
            apply_combobox_theme(combo, theme_name)

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
