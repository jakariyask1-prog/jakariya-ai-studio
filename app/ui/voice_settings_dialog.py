from __future__ import annotations

import logging
import threading
from typing import Any

from PySide6.QtCore import Qt, QTimer
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
    QMessageBox,
)
from PySide6.QtMultimedia import QMediaDevices
from app.voice import VoiceSettings, VoiceController
from app.ui.styles import get_dialog_style, get_theme_palette
from app.ui.add_voice_dialog import AddVoiceDialog
from app.voice.voice_presets import (
    get_voices_for_provider,
    get_default_voice_for_provider,
)

logger = logging.getLogger(__name__)


class VoiceSettingsDialog(QDialog):
    """Voice Settings configuration dialog."""

    def __init__(self, settings: VoiceSettings, controller: VoiceController, parent=None, theme: str = "light") -> None:
        super().__init__(parent)
        self._controller = controller
        self._theme = str(theme).lower()
        self._custom_voices: list[dict[str, Any]] = list(getattr(settings, "custom_voices", []) or [])
        self._is_testing: bool = False
        p = get_theme_palette(self._theme)

        self.setWindowTitle("Voice Settings")
        self.resize(520, 520)
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
        for prov in self._controller._manager.service.available_stt_providers():
            self.stt_combo.addItem(prov.display_name, prov.provider_id)

        # TTS Provider Selector
        self.tts_combo = QComboBox()
        for prov in self._controller._manager.service.available_tts_providers():
            self.tts_combo.addItem(prov.display_name, prov.provider_id)
        self.tts_combo.currentIndexChanged.connect(self._on_tts_combo_changed)

        # Voice Selector + Add Button
        voice_row = QHBoxLayout()
        voice_row.setSpacing(8)

        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(260)
        voice_row.addWidget(self.voice_combo, stretch=1)

        self.btn_add_voice = QPushButton("➕ Add Voice ID")
        self.btn_add_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_voice.setStyleSheet(f"""
            QPushButton {{
                background-color: #4F46E5;
                color: #FFFFFF;
                font-weight: 600;
                padding: 6px 12px;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: #4338CA; }}
        """)
        self.btn_add_voice.clicked.connect(self._open_add_voice_dialog)
        voice_row.addWidget(self.btn_add_voice)

        self.btn_test_voice = QPushButton("🔊 Test")
        self.btn_test_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test_voice.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #FFFFFF;
                font-weight: 600;
                padding: 6px 12px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_test_voice.clicked.connect(self._test_voice)
        voice_row.addWidget(self.btn_test_voice)

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
        provider_layout.addRow("AI Voice:", voice_row)
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
        self.cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {p['btn_secondary_bg']};
                color: {p['btn_secondary_text']};
                border: 1px solid {p['btn_secondary_border']};
                border-radius: 8px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {p['btn_secondary_hover']};
                color: {p['input_text']};
                border-color: {p['border_capsule_focus']};
            }}
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

    def _refresh_voice_combo(self, target_voice_id: str | None = None) -> None:
        """Update voice combo based on active TTS engine."""
        current_tts = self.tts_combo.currentData() or "edge_neural_tts"
        voices = get_voices_for_provider(current_tts, self._custom_voices)

        desired_id = target_voice_id or self.voice_combo.currentData() or get_default_voice_for_provider(current_tts)

        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()

        selected_idx = -1
        for idx, (label, v_id) in enumerate(voices):
            self.voice_combo.addItem(label, v_id)
            if v_id == desired_id:
                selected_idx = idx

        if selected_idx < 0 and desired_id:
            self.voice_combo.addItem(f"Custom ({desired_id})", desired_id)
            selected_idx = self.voice_combo.count() - 1

        if selected_idx >= 0:
            self.voice_combo.setCurrentIndex(selected_idx)
        elif self.voice_combo.count() > 0:
            self.voice_combo.setCurrentIndex(0)

        self.voice_combo.blockSignals(False)

    def _on_tts_combo_changed(self) -> None:
        current_tts = self.tts_combo.currentData() or "edge_neural_tts"
        default_voice = get_default_voice_for_provider(current_tts)
        self._refresh_voice_combo(target_voice_id=default_voice)

    def _open_add_voice_dialog(self) -> None:
        current_provider = self.tts_combo.currentData() or "cartesia"
        dlg = AddVoiceDialog(self, theme=self._theme, default_provider=current_provider)
        if dlg.exec() == AddVoiceDialog.DialogCode.Accepted:
            v_data = dlg.get_voice_data()
            new_id = v_data["id"]

            if not any(str(cv.get("id", "")).strip() == new_id for cv in self._custom_voices):
                self._custom_voices.append(v_data)

            target_prov = v_data.get("provider_id")
            if target_prov:
                idx = self.tts_combo.findData(target_prov)
                if idx >= 0:
                    self.tts_combo.setCurrentIndex(idx)

            self._refresh_voice_combo(target_voice_id=new_id)

    def _test_voice(self) -> None:
        if self._is_testing:
            return

        provider_id = self.tts_combo.currentData() or "edge_neural_tts"
        voice_id = self.voice_combo.currentData() or ""
        language = self.lang_combo.currentData() or "bn"

        self._is_testing = True
        self.btn_test_voice.setEnabled(False)
        self.btn_test_voice.setText("⏳ Testing...")

        def _worker():
            try:
                from app.voice.business_logic.tts.edge_neural_tts import EdgeNeuralTTS
                from app.voice.business_logic.tts.cartesia_tts import CartesiaTTS
                from app.voice.business_logic.tts.elevenlabs_tts import ElevenLabsTTS
                from app.voice.business_logic.tts.fish_audio_tts import FishAudioTTS
                from app.voice.business_logic.tts.google_tts import GoogleTTS

                if provider_id == "cartesia":
                    provider = CartesiaTTS(voice_id=voice_id)
                elif provider_id == "elevenlabs":
                    provider = ElevenLabsTTS(voice_id=voice_id)
                elif provider_id == "fish_audio":
                    provider = FishAudioTTS(voice_id=voice_id)
                elif provider_id == "google_tts":
                    provider = GoogleTTS()
                else:
                    provider = EdgeNeuralTTS()

                if not provider.is_available():
                    if provider_id == "cartesia":
                        raise RuntimeError("Cartesia API key missing or invalid in Settings -> AI Providers.")
                    elif provider_id == "elevenlabs":
                        raise RuntimeError("ElevenLabs API key missing in Settings -> AI Providers.")
                    elif provider_id == "fish_audio":
                        raise RuntimeError("Fish Audio API key missing in Settings -> AI Providers.")

                sample = "হ্যালো, ভয়েস পরীক্ষা সফল হয়েছে!" if language == "bn" else "Hello, voice test was successful!"
                audio = provider.synthesise(sample, language=language)
                if not audio:
                    raise RuntimeError("TTS returned empty audio.")

                self._play_audio(audio)

                def _done():
                    self._is_testing = False
                    self.btn_test_voice.setEnabled(True)
                    self.btn_test_voice.setText("🔊 Test")

                QTimer.singleShot(0, _done)

            except Exception as exc:
                err_text = str(exc)
                logger.warning("[VoiceSettingsDialog] Test voice error: %s", err_text)

                def _err():
                    self._is_testing = False
                    self.btn_test_voice.setEnabled(True)
                    self.btn_test_voice.setText("🔊 Test")
                    if "402" in err_text or "credits limit" in err_text.lower() or "quota" in err_text.lower():
                        QMessageBox.warning(
                            self,
                            "Cartesia Credits Limit Reached (402)",
                            "Your Cartesia AI account has exceeded its model credits limit (HTTP 402).\n\n"
                            "• Please recharge at https://play.cartesia.ai/subscription\n"
                            "• Or select 'Edge Neural TTS' which is 100% free with no credit limits.",
                        )
                    else:
                        QMessageBox.warning(self, "Voice Test Failed", f"Could not play voice preview:\n\n{err_text}")

                QTimer.singleShot(0, _err)

        threading.Thread(target=_worker, daemon=True).start()

    def _play_audio(self, pcm_bytes: bytes) -> None:
        try:
            from PySide6.QtMultimedia import QAudioSink, QAudioFormat, QMediaDevices
            from PySide6.QtCore import QByteArray, QBuffer, QIODevice

            qt_format = QAudioFormat()
            qt_format.setSampleRate(16000)
            qt_format.setChannelCount(1)
            qt_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

            sink = QAudioSink(QMediaDevices.defaultAudioOutput(), qt_format, self)
            buf = QBuffer(self)
            buf.setData(QByteArray(pcm_bytes))
            buf.open(QIODevice.OpenModeFlag.ReadOnly)
            sink.start(buf)
            self._preview_sink = sink
            self._preview_buf = buf
        except Exception as exc:
            logger.debug("[VoiceSettingsDialog] Audio playback error: %s", exc)

    def _load_settings(self, settings: VoiceSettings) -> None:
        """Populate widgets with current voice settings values."""
        self._custom_voices = list(getattr(settings, "custom_voices", []) or [])

        # STT Selection
        idx = self.stt_combo.findData(settings.stt_provider_id)
        if idx >= 0:
            self.stt_combo.setCurrentIndex(idx)

        # TTS Selection
        idx = self.tts_combo.findData(settings.tts_provider_id)
        if idx >= 0:
            self.tts_combo.setCurrentIndex(idx)

        # Refresh voices for this TTS provider and select current voice_id
        target_v = getattr(settings, "voice_id", None)
        self._refresh_voice_combo(target_voice_id=target_v)

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
        current_tts = self.tts_combo.currentData() or "edge_neural_tts"
        return VoiceSettings(
            stt_provider_id=self.stt_combo.currentData(),
            tts_provider_id=current_tts,
            voice_id=self.voice_combo.currentData() or get_default_voice_for_provider(current_tts),
            custom_voices=list(self._custom_voices),
            language=self.lang_combo.currentData(),
            input_device_index=self.mic_combo.currentData(),
            output_device_index=self.speaker_combo.currentData(),
            voice_response=self.voice_response_cb.isChecked(),
            auto_send=self.auto_send_cb.isChecked(),
        )
