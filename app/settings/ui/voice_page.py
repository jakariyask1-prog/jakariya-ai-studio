"""Voice and Audio settings page widget for Jakariya AI Studio."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.settings.settings_schema import VoiceSettingsSchema


class VoiceSettingsPage(QWidget):
    """Voice configuration page: STT/TTS engine selection, language, and VAD thresholds."""

    setting_changed = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Provider & Model Selection Group
        prov_group = QGroupBox("Voice Engines & Voice Selection")
        prov_form = QFormLayout(prov_group)
        prov_form.setContentsMargins(15, 20, 15, 20)
        prov_form.setSpacing(15)

        self.stt_combo = QComboBox()
        self.stt_combo.addItem("Google Web Speech STT (Free & Fast)", "google_stt")
        self.stt_combo.currentIndexChanged.connect(self._on_changed)
        prov_form.addRow("STT Provider:", self.stt_combo)

        self.tts_combo = QComboBox()
        self.tts_combo.addItem("Edge Neural TTS (Free Nabanita / Jenny - Recommended)", "edge_neural_tts")
        self.tts_combo.addItem("Google gTTS (Basic Fallback)", "google_tts")
        self.tts_combo.addItem("Cartesia AI (Sonic Ultra-Fast)", "cartesia")
        self.tts_combo.addItem("Fish Audio TTS", "fish_audio")
        self.tts_combo.currentIndexChanged.connect(self._on_changed)
        prov_form.addRow("TTS Provider:", self.tts_combo)

        self.voice_id_edit = QLineEdit()
        self.voice_id_edit.setPlaceholderText("bn-BD-NabanitaNeural")
        self.voice_id_edit.textChanged.connect(self._on_changed)
        prov_form.addRow("Voice ID / Speaker:", self.voice_id_edit)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("বাংলা (Bangla / bn-BD)", "bn")
        self.lang_combo.addItem("English (US / en-US)", "en")
        self.lang_combo.currentIndexChanged.connect(self._on_changed)
        prov_form.addRow("Voice Language:", self.lang_combo)

        layout.addWidget(prov_group)

        # Behavior & Sensitivity Group
        sens_group = QGroupBox("Voice Behavior & VAD Sensitivity")
        sens_form = QFormLayout(sens_group)
        sens_form.setContentsMargins(15, 20, 15, 20)
        sens_form.setSpacing(15)

        self.auto_send_check = QCheckBox("Automatically send query when user stops speaking")
        self.auto_send_check.toggled.connect(self._on_changed)
        sens_form.addRow("Auto Send:", self.auto_send_check)

        self.response_voice_check = QCheckBox("Speak AI responses aloud using TTS")
        self.response_voice_check.toggled.connect(self._on_changed)
        sens_form.addRow("Voice Response:", self.response_voice_check)

        # Silence Timeout Slider
        timeout_row = QHBoxLayout()
        self.timeout_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeout_slider.setRange(500, 5000)
        self.timeout_slider.setSingleStep(100)
        self.timeout_label = QLabel("1300 ms")
        self.timeout_label.setFixedWidth(65)
        self.timeout_slider.valueChanged.connect(self._on_timeout_changed)
        timeout_row.addWidget(self.timeout_slider)
        timeout_row.addWidget(self.timeout_label)
        sens_form.addRow("Silence Timeout:", timeout_row)

        # VAD Threshold Slider
        vad_row = QHBoxLayout()
        self.vad_slider = QSlider(Qt.Orientation.Horizontal)
        self.vad_slider.setRange(1, 100)
        self.vad_slider.setSingleStep(1)
        self.vad_label = QLabel("0.008")
        self.vad_label.setFixedWidth(65)
        self.vad_slider.valueChanged.connect(self._on_vad_changed)
        vad_row.addWidget(self.vad_slider)
        vad_row.addWidget(self.vad_label)
        sens_form.addRow("VAD Sensitivity:", vad_row)

        layout.addWidget(sens_group)
        layout.addStretch()

    def _on_timeout_changed(self, val: int) -> None:
        self.timeout_label.setText(f"{val} ms")
        self._on_changed()

    def _on_vad_changed(self, val: int) -> None:
        self.vad_label.setText(f"{val / 1000.0:.3f}")
        self._on_changed()

    def _on_changed(self) -> None:
        self.setting_changed.emit("voice", self.get_settings())

    def load_settings(self, settings: VoiceSettingsSchema) -> None:
        self.blockSignals(True)
        stt_idx = self.stt_combo.findData(settings.stt_provider_id)
        if stt_idx >= 0:
            self.stt_combo.setCurrentIndex(stt_idx)

        tts_idx = self.tts_combo.findData(settings.tts_provider_id)
        if tts_idx >= 0:
            self.tts_combo.setCurrentIndex(tts_idx)

        self.voice_id_edit.setText(settings.voice_id)

        lang_idx = self.lang_combo.findData(settings.language)
        if lang_idx >= 0:
            self.lang_combo.setCurrentIndex(lang_idx)

        self.auto_send_check.setChecked(settings.auto_send)
        self.response_voice_check.setChecked(settings.voice_response)
        self.timeout_slider.setValue(settings.silence_timeout_ms)
        self.timeout_label.setText(f"{settings.silence_timeout_ms} ms")

        vad_val = int(settings.vad_threshold * 1000)
        self.vad_slider.setValue(max(1, min(100, vad_val)))
        self.vad_label.setText(f"{settings.vad_threshold:.3f}")
        self.blockSignals(False)

    def get_settings(self) -> VoiceSettingsSchema:
        return VoiceSettingsSchema(
            stt_provider_id=self.stt_combo.currentData() or "google_stt",
            tts_provider_id=self.tts_combo.currentData() or "edge_neural_tts",
            voice_id=self.voice_id_edit.text().strip() or "bn-BD-NabanitaNeural",
            auto_send=self.auto_send_check.isChecked(),
            voice_response=self.response_voice_check.isChecked(),
            silence_timeout_ms=self.timeout_slider.value(),
            vad_threshold=self.vad_slider.value() / 1000.0,
            language=self.lang_combo.currentData() or "bn",
        )


VoicePage = VoiceSettingsPage
