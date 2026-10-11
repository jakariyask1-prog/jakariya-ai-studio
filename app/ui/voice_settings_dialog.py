from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QLabel,
    QGroupBox,
    QPushButton,
    QHBoxLayout,
)
from PySide6.QtMultimedia import QMediaDevices
from app.voice import VoiceSettings, VoiceController
from app.ui.styles import get_dialog_style, get_theme_palette


class VoiceSettingsDialog(QDialog):
    """Voice Settings configuration dialog."""

    def __init__(self, settings: VoiceSettings, controller: VoiceController, parent=None, theme: str = "light") -> None:
        super().__init__(parent)
        self._controller = controller
        self._theme = str(theme).lower()
        p = get_theme_palette(self._theme)

        self.setWindowTitle("Voice Settings")
        self.resize(480, 480)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowMaximizeButtonHint)
        self.setStyleSheet(get_dialog_style(self._theme))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header Title
        title_label = QLabel("🎙️ Configure Audio & Voice Options")
        title_label.setStyleSheet(f"font-size: 15pt; font-weight: 800; color: {p['input_text']}; margin-bottom: 6px;")
        layout.addWidget(title_label)


        # Group 1: Providers & Language
        provider_group = QGroupBox("Providers & Language")
        provider_layout = QFormLayout(provider_group)
        provider_layout.setSpacing(10)
        provider_layout.setContentsMargins(14, 14, 14, 14)

        # STT Provider Selector
        self.stt_combo = QComboBox()
        for p in self._controller._manager.service.available_stt_providers():
            self.stt_combo.addItem(p.display_name, p.provider_id)
        
        # TTS Provider Selector
        self.tts_combo = QComboBox()
        for p in self._controller._manager.service.available_tts_providers():
            self.tts_combo.addItem(p.display_name, p.provider_id)

        # Voice Selector (ElevenLabs / Neural Voices)
        self.voice_combo = QComboBox()
        curated_voices = [
            ("⭐ Personal Voice - Bangla (Cartesia AI Cloned Voice)", "2c8d7dfb-ca84-4888-9600-8d8c54022dba"),
            ("⭐ Personal Voice - English (Cartesia AI Cloned Voice)", "e8299d96-b115-4ed1-80aa-2696eb5335ca"),
            ("👩 Sarah (Warm & Expressive - Best for Bangla & English)", "EXAVITQu4vr4xnSDxMaL"),
            ("👨 Adam (Deep, Confident & Clear - Best for English & Bangla)", "pNInz6obpgDQGcFmaJgB"),
            ("👩 Alice (Clear & Professional)", "Xb7hH8MSUJpSbSDYk0k2"),
            ("👨 George (Warm & Resonant)", "JBFqnCBsd6RMkjVDRZzb"),
            ("👩 Lily (Soft, Velvety & Gentle)", "pFZP5JQG7iQjIQuC4Bku"),
            ("👨 Daniel (Deep & Authoritative)", "onwK4e9ZLuTAKqWW03F9"),
            ("👩 Jessica (Bright & Youthful)", "cgSgspJ2msm6clMCkdW9"),
            ("👨 Bill (Trustworthy & Confident)", "pqHfZKP75CvOlQylNhV4"),
            ("👩 Matilda (Warm & Friendly)", "XrExE9yKIg1WjnnlVkGX"),
            ("👨 Liam (Dynamic & Modern)", "TX3LPaxmHKxFdv7VOQHJ"),
        ]
        for v_label, v_id in curated_voices:
            self.voice_combo.addItem(v_label, v_id)

        # Language Selector
        self.lang_combo = QComboBox()
        languages = [
            ("Bangla (Bengali)", "bn"),
            ("English", "en"),
            ("Spanish", "es"),
            ("French", "fr"),
            ("German", "de"),
            ("Hindi", "hi"),
            ("Japanese", "ja"),
            ("Korean", "ko"),
            ("Portuguese", "pt"),
            ("Chinese", "zh"),
            ("Arabic", "ar"),
        ]
        for name, code in languages:
            self.lang_combo.addItem(f"🌐 {name}", code)

        provider_layout.addRow("STT Engine:", self.stt_combo)
        provider_layout.addRow("TTS Engine:", self.tts_combo)
        provider_layout.addRow("AI Voice:", self.voice_combo)
        provider_layout.addRow("Language:", self.lang_combo)
        layout.addWidget(provider_group)

        # Group 2: Devices
        device_group = QGroupBox("Hardware Devices")
        device_layout = QFormLayout(device_group)
        device_layout.setSpacing(10)
        device_layout.setContentsMargins(14, 14, 14, 14)

        # Input (Microphone) Selector
        self.mic_combo = QComboBox()
        self.mic_combo.addItem("🎙️ System Default Microphone", None)
        inputs = QMediaDevices.audioInputs()
        for idx, dev in enumerate(inputs):
            self.mic_combo.addItem(f"🎙️ {dev.description()}", idx)

        # Output (Speaker) Selector
        self.speaker_combo = QComboBox()
        self.speaker_combo.addItem("🔊 System Default Speaker", None)
        outputs = QMediaDevices.audioOutputs()
        for idx, dev in enumerate(outputs):
            self.speaker_combo.addItem(f"🔊 {dev.description()}", idx)

        device_layout.addRow("Input (Mic):", self.mic_combo)
        device_layout.addRow("Output (Speaker):", self.speaker_combo)
        layout.addWidget(device_group)

        # Group 3: Behavior Flags
        behavior_group = QGroupBox("Settings & Behavior")
        behavior_layout = QVBoxLayout(behavior_group)
        behavior_layout.setSpacing(10)
        behavior_layout.setContentsMargins(16, 14, 16, 14)

        self.voice_response_cb = QCheckBox("Enable Voice Output (TTS Response)")
        self.auto_send_cb = QCheckBox("Auto-send transcribed voice messages")

        behavior_layout.addWidget(self.voice_response_cb)
        behavior_layout.addWidget(self.auto_send_cb)
        layout.addWidget(behavior_group)

        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedHeight(38)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #E2E8F0; color: #0F172A; }
        """)
        self.cancel_button.clicked.connect(self.reject)

        self.save_button = QPushButton("Save Settings")
        self.save_button.setFixedHeight(38)
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        self.save_button.clicked.connect(self.accept)

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)

        # Load Current Values
        self._load_settings(settings)

    def _load_settings(self, settings: VoiceSettings) -> None:
        """Populate widgets with current voice settings values."""
        # STT Selection
        idx = self.stt_combo.findData(settings.stt_provider_id)
        if idx >= 0:
            self.stt_combo.setCurrentIndex(idx)

        # TTS Selection
        idx = self.tts_combo.findData(settings.tts_provider_id)
        if idx >= 0:
            self.tts_combo.setCurrentIndex(idx)

        # Voice Selection
        if hasattr(settings, "voice_id") and settings.voice_id:
            idx = self.voice_combo.findData(settings.voice_id)
            if idx >= 0:
                self.voice_combo.setCurrentIndex(idx)
            else:
                self.voice_combo.addItem(f"Custom ({settings.voice_id})", settings.voice_id)
                self.voice_combo.setCurrentIndex(self.voice_combo.count() - 1)

        # Language Selection
        idx = self.lang_combo.findData(settings.language)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)

        # Microphone Selection
        if settings.input_device_index is not None:
            idx = self.mic_combo.findData(settings.input_device_index)
            if idx >= 0:
                self.mic_combo.setCurrentIndex(idx)
        else:
            self.mic_combo.setCurrentIndex(0)

        # Speaker Selection
        if settings.output_device_index is not None:
            idx = self.speaker_combo.findData(settings.output_device_index)
            if idx >= 0:
                self.speaker_combo.setCurrentIndex(idx)
        else:
            self.speaker_combo.setCurrentIndex(0)

        # Checkboxes
        self.voice_response_cb.setChecked(settings.voice_response)
        self.auto_send_cb.setChecked(settings.auto_send)

    def get_settings(self) -> VoiceSettings:
        """Construct and return a VoiceSettings object from current UI selections."""
        return VoiceSettings(
            stt_provider_id=self.stt_combo.currentData(),
            tts_provider_id=self.tts_combo.currentData(),
            voice_id=self.voice_combo.currentData() or "EXAVITQu4vr4xnSDxMaL",
            language=self.lang_combo.currentData(),
            input_device_index=self.mic_combo.currentData(),
            output_device_index=self.speaker_combo.currentData(),
            voice_response=self.voice_response_cb.isChecked(),
            auto_send=self.auto_send_cb.isChecked(),
        )
