"""Microphone discovery, device selection, and audio recording management.

Manages audio input hardware discovery using QtMultimedia (with safe fallbacks)
and handles audio recording and level monitoring for the voice pipeline.
"""

from __future__ import annotations

import time
import logging
import array
from dataclasses import dataclass

from PySide6.QtCore import QIODevice, QObject, Signal, QTimer
from PySide6.QtMultimedia import (
    QAudioFormat,
    QAudioSource,
    QMediaDevices,
)

from app.voice.business_logic.audio.audio_stream import AudioFormat, AudioStream


@dataclass(frozen=True)
class AudioDevice:
    """Representation of an audio input or output hardware device."""

    device_id: str
    name: str
    is_default: bool = False
    is_input: bool = True
    sample_rates: tuple[int, ...] = (16000, 44100, 48000)
    channels: int = 1


class MicrophoneManager(QObject):
    """Manage audio input discovery and recording capture."""

    recording_started = Signal()
    recording_stopped = Signal()
    audio_chunk_captured = Signal(bytes)
    level_updated = Signal(float)
    speech_started = Signal()
    silence_detected = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._selected_device_id: str | None = None
        self._is_recording: bool = False
        self._audio_stream: AudioStream = AudioStream()
        self._audio_source: QAudioSource | None = None
        self._gain: float = 1.0
        self._io_device: QIODevice | None = None
        
        # VAD & Silence Detection Configuration
        self._speech_started_flag: bool = False
        self._speech_consecutive_chunks: int = 0
        self._recording_start_time: float = 0.0
        self._is_capturing: bool = True
        self._barge_in_monitoring: bool = False
        
        self._silence_timer = QTimer(self)
        self._silence_timer.setSingleShot(True)
        self._silence_timer.timeout.connect(self._on_silence_timeout)
        self.silence_timeout_ms: int = 1000  # 1000ms natural silence pause for conversational speech
        self.vad_threshold: float = 0.012    # Responsive VAD threshold to pick up normal human voice

    @property
    def is_recording(self) -> bool:
        """Return ``True`` if microphone capture is currently active."""
        return self._is_recording

    @property
    def is_capturing(self) -> bool:
        """Return ``True`` if incoming PCM audio is actively being buffered for speech recognition."""
        return self._is_capturing

    @is_capturing.setter
    def is_capturing(self, enabled: bool) -> None:
        self._is_capturing = bool(enabled)
        if not self._is_capturing:
            self._speech_started_flag = False
            self._speech_consecutive_chunks = 0
            self._silence_timer.stop()

    @property
    def barge_in_monitoring(self) -> bool:
        """Return ``True`` if barge-in monitoring is active during AI playback."""
        return self._barge_in_monitoring

    @barge_in_monitoring.setter
    def barge_in_monitoring(self, enabled: bool) -> None:
        self._barge_in_monitoring = bool(enabled)
        self._speech_consecutive_chunks = 0

    @property
    def current_stream(self) -> AudioStream:
        """Return the active or last captured audio stream."""
        return self._audio_stream

    @property
    def current_level(self) -> float:
        """Return the current smoothed RMS audio level (0.0 to 1.0)."""
        return self._audio_stream.current_level

    # ------------------------------------------------------------------
    # Device Discovery & Selection
    # ------------------------------------------------------------------

    def list_devices(self) -> list[AudioDevice]:
        devices: list[AudioDevice] = []
        try:
            qt_inputs = QMediaDevices.audioInputs()
            default_device = QMediaDevices.defaultAudioInput()
            default_id = bytes(default_device.id()).decode("utf-8", errors="ignore") if default_device else ""

            for qt_dev in qt_inputs:
                dev_id = bytes(qt_dev.id()).decode("utf-8", errors="ignore")
                name = qt_dev.description() or "Default Microphone"
                is_def = (dev_id == default_id) or qt_dev.isDefault()
                devices.append(
                    AudioDevice(
                        device_id=dev_id,
                        name=name,
                        is_default=is_def,
                        is_input=True,
                    )
                )
        except Exception:
            pass

        if not devices:
            devices.append(
                AudioDevice(
                    device_id="default_mic",
                    name="Default Microphone",
                    is_default=True,
                    is_input=True,
                )
            )

        return devices

    def select_device(self, device_id: str | None) -> None:
        self._selected_device_id = device_id

    def set_gain(self, gain: float) -> None:
        """Set digital gain multiplier for incoming audio data."""
        self._gain = gain
        logging.debug(f"[MicrophoneManager] Digital gain set to {gain}")

    def get_wav_and_clear(self) -> bytes:
        """Retrieve current WAV bytes and clear the buffer without stopping recording."""
        wav_bytes = self._audio_stream.get_wav_bytes()
        self._audio_stream.clear()
        # Reset speech state and stop silence timer for safety
        self._speech_started_flag = False
        self._speech_consecutive_chunks = 0
        self._silence_timer.stop()
        if self._io_device:
            try:
                self._io_device.readAll()
            except Exception:
                pass
        return wav_bytes

    # ------------------------------------------------------------------
    # Recording Control
    # ------------------------------------------------------------------

    def start_recording(self, sample_rate: int = 16000) -> bool:
        logging.debug(f"[MicrophoneManager] start_recording called: is_recording={self._is_recording}")
        self._gain = 1.0  # Reset gain back to 1.0 for new recording
        self._is_capturing = True
        self._barge_in_monitoring = False
        if self._is_recording:
            self._audio_stream.clear()
            self._speech_started_flag = False
            self._speech_consecutive_chunks = 0
            self._recording_start_time = time.time()
            self._silence_timer.stop()
            if self._io_device:
                try:
                    self._io_device.readAll()  # Flush leftover PCM audio from previous turn
                except Exception:
                    pass
            self.recording_started.emit()
            return True

        audio_format = AudioFormat(sample_rate=sample_rate, channels=1, bits_per_sample=16)
        self._audio_stream = AudioStream(audio_format)
        self._is_recording = True
        self._is_capturing = True
        self._barge_in_monitoring = False
        self._speech_started_flag = False
        self._speech_consecutive_chunks = 0
        self._recording_start_time = time.time()
        self._silence_timer.stop()

        try:
            qt_format = QAudioFormat()
            qt_format.setSampleRate(sample_rate)
            qt_format.setChannelCount(1)
            qt_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

            target_qt_dev = QMediaDevices.defaultAudioInput()
            settings = None
            if self.parent() and hasattr(self.parent(), "settings"):
                settings = self.parent().settings

            if settings and settings.input_device_index is not None:
                inputs = QMediaDevices.audioInputs()
                if 0 <= settings.input_device_index < len(inputs):
                    target_qt_dev = inputs[settings.input_device_index]
            elif self._selected_device_id:
                for dev in QMediaDevices.audioInputs():
                    dev_id = bytes(dev.id()).decode("utf-8", errors="ignore")
                    if dev_id == self._selected_device_id:
                        target_qt_dev = dev
                        break

            logging.debug(f"[MicrophoneManager] Creating QAudioSource for device: {target_qt_dev.description()}")
            self._audio_source = QAudioSource(target_qt_dev, qt_format, self)
            self._audio_source.setBufferSize(3200)  # 100ms low-latency frame buffer at 16kHz 16-bit mono
            self._io_device = self._audio_source.start()
            if self._io_device:
                self._io_device.readyRead.connect(self._on_ready_read)
                logging.debug("[MicrophoneManager] readyRead connected — recording active")
            else:
                logging.error("[MicrophoneManager] QAudioSource.start() returned None — recording FAILED")
                self._is_recording = False
                self._audio_source.deleteLater()
                self._audio_source = None
                return False
        except Exception as e:
            logging.exception(f"[MicrophoneManager] start_recording exception: {e}")
            self._is_recording = False
            if self._audio_source:
                self._audio_source.deleteLater()
            self._audio_source = None
            self._io_device = None
            return False

        self.recording_started.emit()
        return True

    def stop_recording(self) -> bytes:
        logging.debug(f"[MicrophoneManager] stop_recording called: is_recording={self._is_recording}")
        if not self._is_recording:
            return self._audio_stream.get_wav_bytes()

        self._is_recording = False
        self._is_capturing = False
        self._barge_in_monitoring = False
        self._speech_started_flag = False
        self._speech_consecutive_chunks = 0
        self._silence_timer.stop()

        if self._audio_source:
            try:
                if self._io_device:
                    try:
                        self._io_device.readyRead.disconnect(self._on_ready_read)
                    except Exception:
                        pass
                self._audio_source.stop()
                self._audio_source.deleteLater()
            except Exception as e:
                logging.exception(f"[MicrophoneManager] stop_recording cleanup error: {e}")
            self._audio_source = None
            self._io_device = None

        wav_bytes = self._audio_stream.get_wav_bytes()
        self.recording_stopped.emit()
        logging.debug(f"[MicrophoneManager] recording_stopped emitted, wav={len(wav_bytes)} bytes")
        return wav_bytes

    def get_audio_data(self) -> bytes:
        return self._audio_stream.get_raw_bytes()

    def process_pcm_chunk(self, pcm_bytes: bytes) -> float:
        # If not actively capturing for STT (e.g. AI is speaking or thinking), isolate buffer
        if not self._is_capturing:
            level = self._audio_stream._level_meter.update(pcm_bytes)
            self.level_updated.emit(level)

            # Barge-in monitoring: Only triggers on genuine, loud user speech (>0.12 RMS for ~600ms)
            # This completely prevents laptop speaker output from triggering false barge-in.
            if self._barge_in_monitoring:
                if level > 0.12:
                    self._speech_consecutive_chunks += 1
                    if self._speech_consecutive_chunks >= 6:
                        self._speech_consecutive_chunks = 0
                        self.speech_started.emit()
                else:
                    self._speech_consecutive_chunks = max(0, self._speech_consecutive_chunks - 1)
            return level

        chunk = self._audio_stream.append(pcm_bytes)
        self.audio_chunk_captured.emit(pcm_bytes)
        self.level_updated.emit(chunk.rms_level)
        
        # Ignore initial 40ms buffer pop/noise right after mic start
        elapsed = time.time() - self._recording_start_time
        if elapsed < 0.04:
            return chunk.rms_level

        effective_threshold = self.vad_threshold
        min_consecutive_chunks = 2

        if chunk.rms_level > effective_threshold:
            self._speech_consecutive_chunks += 1
            if self._speech_consecutive_chunks >= min_consecutive_chunks:
                if not self._speech_started_flag:
                    self._speech_started_flag = True
                    self.speech_started.emit()
                self._silence_timer.stop()
        else:
            # Graceful decay instead of hard reset to 0 so natural speech consonants/pauses don't abort onset detection
            self._speech_consecutive_chunks = max(0, self._speech_consecutive_chunks - 1)
            if self._speech_started_flag and not self._silence_timer.isActive():
                self._silence_timer.start(self.silence_timeout_ms)
                
        return chunk.rms_level

    # ------------------------------------------------------------------
    # Internal Slots
    # ------------------------------------------------------------------

    def _on_silence_timeout(self) -> None:
        """Triggered when RMS level stays below threshold for silence_timeout_ms."""
        if not self._is_recording or not self._speech_started_flag:
            return

        # Require at least 6400 bytes (~200ms) of audio to consider it real speech.
        # Short noise pops/clicks will be safely ignored and VAD reset for next turn,
        # while short words ("হ্যাঁ", "না", "hi", "yes") are reliably captured.
        raw_bytes = self._audio_stream.get_raw_bytes()
        if len(raw_bytes) < 6400:
            logging.debug("[MicrophoneManager] Short ambient noise — resetting VAD state for next turn")
            self._speech_started_flag = False
            self._speech_consecutive_chunks = 0
            self._silence_timer.stop()
            return

        self._speech_started_flag = False
        self._speech_consecutive_chunks = 0
        self.silence_detected.emit()

    def _on_ready_read(self) -> None:
        if not self._io_device or not self._is_recording:
            return

        try:
            pcm_bytes = bytes(self._io_device.readAll())
            if pcm_bytes:
                if self._gain != 1.0:
                    arr = array.array('h', pcm_bytes)
                    for i in range(len(arr)):
                        val = int(arr[i] * self._gain)
                        if val > 32767:
                            val = 32767
                        elif val < -32768:
                            val = -32768
                        arr[i] = val
                    pcm_bytes = arr.tobytes()
                self.process_pcm_chunk(pcm_bytes)
        except Exception:
            pass
