"""Voice and Audio settings page widget for Jakariya AI Studio."""

from __future__ import annotations

import logging
import threading
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.settings.settings_schema import VoiceSettingsSchema
from app.ui.add_voice_dialog import AddVoiceDialog
from app.voice.voice_presets import (
    get_default_voice_for_provider,
    get_voices_for_provider,
)

logger = logging.getLogger(__name__)


class VoiceSettingsPage(QWidget):
    """Voice configuration page: STT/TTS engine selection, preset & custom voice management, and VAD thresholds."""

    setting_changed = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._custom_voices: list[dict[str, Any]] = []
        self._is_testing: bool = False
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

        # 1. STT Provider
        self.stt_combo = QComboBox()
        self.stt_combo.addItem("Google Web Speech STT (Free & Fast)", "google_stt")
        self.stt_combo.currentIndexChanged.connect(self._on_changed)
        prov_form.addRow("STT Provider:", self.stt_combo)

        # 2. TTS Provider
        self.tts_combo = QComboBox()
        self.tts_combo.addItem("Edge Neural TTS (Free Nabanita / Jenny - Recommended)", "edge_neural_tts")
        self.tts_combo.addItem("Cartesia AI (Sonic Ultra-Fast Cloned Voice)", "cartesia")
        self.tts_combo.addItem("ElevenLabs Multilingual v2 (Natural & Expressive)", "elevenlabs")
        self.tts_combo.addItem("Fish Audio TTS (s2.1-pro)", "fish_audio")
        self.tts_combo.addItem("Google gTTS (Basic Fallback)", "google_tts")
        self.tts_combo.currentIndexChanged.connect(self._on_tts_provider_changed)
        prov_form.addRow("TTS Provider:", self.tts_combo)

        # 3. Voice Selector Row (Dropdown + Add Custom Button + Remove)
        voice_row = QHBoxLayout()
        voice_row.setSpacing(8)

        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(260)
        self.voice_combo.currentIndexChanged.connect(self._on_voice_combo_changed)
        voice_row.addWidget(self.voice_combo, stretch=1)

        self.btn_add_voice = QPushButton("➕ Add Voice ID")
        self.btn_add_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_voice.setToolTip("Add a custom or cloned voice ID from Cartesia, ElevenLabs, etc.")
        self.btn_add_voice.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: #FFFFFF;
                font-weight: 600;
                padding: 6px 12px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        self.btn_add_voice.clicked.connect(self._open_add_voice_dialog)
        voice_row.addWidget(self.btn_add_voice)

        self.btn_remove_voice = QPushButton("🗑️")
        self.btn_remove_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove_voice.setToolTip("Remove selected custom voice")
        self.btn_remove_voice.setFixedWidth(36)
        self.btn_remove_voice.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: #FFFFFF;
                font-weight: 600;
                padding: 6px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #DC2626; }
        """)
        self.btn_remove_voice.clicked.connect(self._remove_selected_custom_voice)
        self.btn_remove_voice.setEnabled(False)
        voice_row.addWidget(self.btn_remove_voice)

        prov_form.addRow("AI Voice / Speaker:", voice_row)

        # 4. Manual Voice ID input & Test Button Row
        id_row = QHBoxLayout()
        id_row.setSpacing(8)

        self.voice_id_edit = QLineEdit()
        self.voice_id_edit.setPlaceholderText("bn-BD-NabanitaNeural")
        self.voice_id_edit.textChanged.connect(self._on_voice_id_text_changed)
        id_row.addWidget(self.voice_id_edit, stretch=1)

        self.btn_test_voice = QPushButton("🔊 Test Voice")
        self.btn_test_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test_voice.setToolTip("Synthesize a short audio preview of this voice")
        self.btn_test_voice.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #FFFFFF;
                font-weight: 600;
                padding: 6px 14px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_test_voice.clicked.connect(self._test_voice)
        id_row.addWidget(self.btn_test_voice)

        prov_form.addRow("Voice ID (Raw):", id_row)

        # Test Status Label
        self.test_status_label = QLabel("")
        self.test_status_label.setWordWrap(True)
        self.test_status_label.setStyleSheet("font-size: 11px; margin-top: -4px;")
        self.test_status_label.setVisible(False)
        prov_form.addRow("", self.test_status_label)

        # 5. Language Selector
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

        # Initial voice dropdown load
        self._refresh_voice_dropdown()

    # ------------------------------------------------------------------
    # Voice Dropdown & Custom Voices Management
    # ------------------------------------------------------------------

    def _refresh_voice_dropdown(self, target_voice_id: str | None = None) -> None:
        """Populate voice dropdown with presets for currently active TTS provider + custom voices."""
        current_provider = self.tts_combo.currentData() or "edge_neural_tts"
        voices = get_voices_for_provider(current_provider, self._custom_voices)

        desired_id = target_voice_id or self.voice_id_edit.text().strip() or get_default_voice_for_provider(current_provider)

        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()

        selected_idx = -1
        for idx, (label, v_id) in enumerate(voices):
            self.voice_combo.addItem(label, v_id)
            if v_id == desired_id:
                selected_idx = idx

        # If desired_id is not in list, add it as manual custom entry
        if selected_idx < 0 and desired_id:
            self.voice_combo.addItem(f"Custom ({desired_id})", desired_id)
            selected_idx = self.voice_combo.count() - 1

        if selected_idx >= 0:
            self.voice_combo.setCurrentIndex(selected_idx)
        elif self.voice_combo.count() > 0:
            self.voice_combo.setCurrentIndex(0)

        self.voice_combo.blockSignals(False)

        # Update raw text box and remove button
        current_data = self.voice_combo.currentData() or desired_id
        self.voice_id_edit.blockSignals(True)
        self.voice_id_edit.setText(current_data)
        self.voice_id_edit.blockSignals(False)

        self._update_remove_button_state()

    def _on_tts_provider_changed(self) -> None:
        """Handle TTS Provider combo change: update voices to match the selected engine."""
        current_provider = self.tts_combo.currentData() or "edge_neural_tts"
        default_voice = get_default_voice_for_provider(current_provider)
        self._refresh_voice_dropdown(target_voice_id=default_voice)
        self.test_status_label.setVisible(False)
        self._on_changed()

    def _on_voice_combo_changed(self) -> None:
        """Handle user selecting a different voice in the dropdown."""
        v_id = self.voice_combo.currentData()
        if v_id is not None:
            self.voice_id_edit.blockSignals(True)
            self.voice_id_edit.setText(str(v_id))
            self.voice_id_edit.blockSignals(False)
            self._update_remove_button_state()
            self._on_changed()

    def _on_voice_id_text_changed(self, text: str) -> None:
        """Handle user typing manually into the Voice ID box."""
        clean_text = text.strip()
        idx = self.voice_combo.findData(clean_text)
        self.voice_combo.blockSignals(True)
        if idx >= 0:
            self.voice_combo.setCurrentIndex(idx)
        else:
            # Custom unlisted voice
            self.voice_combo.setEditText(clean_text)
        self.voice_combo.blockSignals(False)
        self._update_remove_button_state()
        self._on_changed()

    def _update_remove_button_state(self) -> None:
        """Enable remove button only if currently selected voice is in self._custom_voices."""
        current_id = self.voice_id_edit.text().strip()
        is_custom = any(str(cv.get("id", "")).strip() == current_id for cv in self._custom_voices)
        self.btn_remove_voice.setEnabled(is_custom)

    def _open_add_voice_dialog(self) -> None:
        """Open the Add Custom Voice dialog."""
        current_provider = self.tts_combo.currentData() or "cartesia"
        dlg = AddVoiceDialog(self, default_provider=current_provider)
        if dlg.exec() == AddVoiceDialog.DialogCode.Accepted:
            voice_data = dlg.get_voice_data()
            new_id = voice_data["id"]

            # Check for duplicate
            if not any(str(cv.get("id", "")).strip() == new_id for cv in self._custom_voices):
                self._custom_voices.append(voice_data)

            # Switch provider if needed
            target_prov = voice_data.get("provider_id")
            if target_prov:
                idx = self.tts_combo.findData(target_prov)
                if idx >= 0 and idx != self.tts_combo.currentIndex():
                    self.tts_combo.blockSignals(True)
                    self.tts_combo.setCurrentIndex(idx)
                    self.tts_combo.blockSignals(False)

            self._refresh_voice_dropdown(target_voice_id=new_id)
            self._on_changed()

    def _remove_selected_custom_voice(self) -> None:
        """Remove the currently selected custom voice."""
        current_id = self.voice_id_edit.text().strip()
        before_len = len(self._custom_voices)
        self._custom_voices = [cv for cv in self._custom_voices if str(cv.get("id", "")).strip() != current_id]

        if len(self._custom_voices) < before_len:
            current_provider = self.tts_combo.currentData() or "edge_neural_tts"
            default_voice = get_default_voice_for_provider(current_provider)
            self._refresh_voice_dropdown(target_voice_id=default_voice)
            self._on_changed()

    # ------------------------------------------------------------------
    # Test Voice Synthesis
    # ------------------------------------------------------------------

    def _test_voice(self) -> None:
        """Test audio synthesis with currently selected provider and voice ID."""
        if self._is_testing:
            return

        provider_id = self.tts_combo.currentData() or "edge_neural_tts"
        voice_id = self.voice_id_edit.text().strip()
        language = self.lang_combo.currentData() or "bn"

        self._is_testing = True
        self.btn_test_voice.setEnabled(False)
        self.test_status_label.setVisible(True)
        self.test_status_label.setStyleSheet("color: #4F46E5; font-weight: 600;")
        self.test_status_label.setText("⏳ Testing voice audio synthesis...")

        def _worker():
            try:
                # 1. Resolve provider
                from app.voice.business_logic.tts.edge_neural_tts import EdgeNeuralTTS
                from app.voice.business_logic.tts.cartesia_tts import CartesiaTTS
                from app.voice.business_logic.tts.elevenlabs_tts import ElevenLabsTTS
                from app.voice.business_logic.tts.fish_audio_tts import FishAudioTTS
                from app.voice.business_logic.tts.google_tts import GoogleTTS

                provider = None
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

                # Check availability
                if not provider.is_available():
                    if provider_id == "cartesia":
                        raise RuntimeError("Cartesia API key is missing or invalid. Please configure CARTESIA_API_KEY in Settings -> AI Providers.")
                    elif provider_id == "elevenlabs":
                        raise RuntimeError("ElevenLabs API key is missing. Please configure ELEVENLABS_API_KEY in Settings -> AI Providers.")
                    elif provider_id == "fish_audio":
                        raise RuntimeError("Fish Audio API key is missing. Please configure FISH_AUDIO_API_KEY in Settings -> AI Providers.")

                sample_text = (
                    "হ্যালো, এটি জাকারিয়া এআই স্টুডিওর একটি টেস্ট ভয়েস অডিও।"
                    if language == "bn"
                    else "Hello! This is a test preview of your selected AI voice in Jakariya AI Studio."
                )

                audio_bytes = provider.synthesise(sample_text, language=language)
                if not audio_bytes:
                    raise RuntimeError("TTS returned empty audio.")

                # Play preview
                self._play_test_audio(audio_bytes)

                def _on_success():
                    self.test_status_label.setStyleSheet("color: #10B981; font-weight: 600;")
                    self.test_status_label.setText("✅ Voice test successful! 🔊 Audio preview played.")
                    self._is_testing = False
                    self.btn_test_voice.setEnabled(True)

                from PySide6.QtCore import QMetaObject, Qt, Q_ARG
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, _on_success)

            except Exception as exc:
                err_text = str(exc)
                logger.warning("[VoiceSettingsPage] Test voice failed: %s", err_text)

                def _on_error():
                    self.test_status_label.setStyleSheet("color: #EF4444; font-weight: 600;")
                    if "402" in err_text or "credits limit" in err_text.lower() or "quota" in err_text.lower():
                        self.test_status_label.setText(
                            "❌ Cartesia Credits Limit Reached (402 Quota Exceeded). "
                            "Recharge at play.cartesia.ai or switch to Edge Neural TTS (100% Free)."
                        )
                        QMessageBox.warning(
                            self,
                            "Cartesia Credits Limit Reached",
                            "Your Cartesia AI account has exceeded its free model credits limit (HTTP 402).\n\n"
                            "• To use Cartesia: Please upgrade or recharge your subscription at https://play.cartesia.ai/subscription\n"
                            "• Free Alternative: Switch TTS Provider to 'Edge Neural TTS' which is 100% free with no credit limits.",
                        )
                    else:
                        self.test_status_label.setText(f"❌ Synthesis error: {err_text[:120]}")
                        QMessageBox.warning(self, "Voice Test Failed", f"Could not synthesize test audio:\n\n{err_text}")

                    self._is_testing = False
                    self.btn_test_voice.setEnabled(True)

                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, _on_error)

        threading.Thread(target=_worker, daemon=True).start()

    def _play_test_audio(self, pcm_bytes: bytes) -> None:
        """Play PCM audio chunks through speaker using QAudioSink or miniaudio."""
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
            # Retain references so garbage collector doesn't cut playback
            self._preview_sink = sink
            self._preview_buf = buf
        except Exception as exc:
            logger.debug("[VoiceSettingsPage] Preview playback failed: %s", exc)

    # ------------------------------------------------------------------
    # Sliders & General Events
    # ------------------------------------------------------------------

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
        self._custom_voices = list(getattr(settings, "custom_voices", []) or [])

        stt_idx = self.stt_combo.findData(settings.stt_provider_id)
        if stt_idx >= 0:
            self.stt_combo.setCurrentIndex(stt_idx)

        tts_idx = self.tts_combo.findData(settings.tts_provider_id)
        if tts_idx >= 0:
            self.tts_combo.setCurrentIndex(tts_idx)

        self.voice_id_edit.setText(settings.voice_id)
        self._refresh_voice_dropdown(target_voice_id=settings.voice_id)

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
            custom_voices=list(self._custom_voices),
            auto_send=self.auto_send_check.isChecked(),
            voice_response=self.response_voice_check.isChecked(),
            silence_timeout_ms=self.timeout_slider.value(),
            vad_threshold=self.vad_slider.value() / 1000.0,
            language=self.lang_combo.currentData() or "bn",
        )


VoicePage = VoiceSettingsPage
