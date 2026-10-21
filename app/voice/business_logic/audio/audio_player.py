"""Audio playback infrastructure for synthesizing and playing audio streams.

Provides underlying QAudioSink push playback management for TTS audio output.
"""

from __future__ import annotations

import logging
from typing import Any
from PySide6.QtCore import QIODevice, QObject, QTimer, Signal, Slot
from PySide6.QtMultimedia import (
    QAudio,
    QAudioFormat,
    QAudioSink,
    QMediaDevices,
)


class AudioPlayer(QObject):
    """Audio playback engine for playing raw audio buffers using push mode."""

    # Qt Signals for playback state transitions
    playback_started = Signal()
    playback_finished = Signal()
    state_changed = Signal(bool)  # True = playing, False = stopped

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._is_playing: bool = False
        self._audio_sink: QAudioSink | None = None
        self._io_device: QIODevice | None = None
        self._pending_audio: bytes = b""
        self._volume: float = 1.0
        self._stream_complete: bool = False  # True when no more chunks will arrive
        self._stopping: bool = False  # Guard against re-entrant stop()

    @property
    def is_playing(self) -> bool:
        """Return True if audio playback is currently active."""
        return self._is_playing

    @property
    def volume(self) -> float:
        """Return output volume level (0.0 to 1.0)."""
        return self._volume

    def set_volume(self, volume: float) -> None:
        """Set playback volume level."""
        self._volume = max(0.0, min(1.0, volume))
        if self._audio_sink:
            try:
                self._audio_sink.setVolume(self._volume)
            except Exception:
                pass

    BUFFER_THRESHOLD: int = 3200  # ~100ms low-latency pre-buffer at 16kHz 16-bit mono for ultra-responsive playback

    def play_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> bool:
        """Play raw PCM audio bytes using QAudioSink push mode."""
        if not audio_bytes:
            return False

        self.stop()

        try:
            self._stream_complete = False
            self._stopping = False
            self._pending_audio = audio_bytes
            self._sample_rate = sample_rate
            self._channels = channels

            # If initial chunk is small and stream not marked complete, buffer before starting sink
            if len(self._pending_audio) < self.BUFFER_THRESHOLD and not self._stream_complete:
                logging.debug(f"[AudioPlayer] Pre-buffering initial chunk ({len(self._pending_audio)} < {self.BUFFER_THRESHOLD} bytes)")
                return True

            return self._start_sink_and_play()
        except Exception as e:
            logging.exception(f"[AudioPlayer] play_bytes failed: {e}")
            self.stop()
            return False

    def _start_sink_and_play(self) -> bool:
        """Initialize QAudioSink and begin push mode playback."""
        if self._audio_sink:
            return True

        qt_format = QAudioFormat()
        qt_format.setSampleRate(getattr(self, "_sample_rate", 16000))
        qt_format.setChannelCount(getattr(self, "_channels", 1))
        qt_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        target_dev = QMediaDevices.defaultAudioOutput()
        settings = None
        if self.parent() and hasattr(self.parent(), "settings"):
            settings = self.parent().settings
        if settings and settings.output_device_index is not None:
            outputs = QMediaDevices.audioOutputs()
            if 0 <= settings.output_device_index < len(outputs):
                target_dev = outputs[settings.output_device_index]

        if target_dev.isNull():
            logging.error("[AudioPlayer] Target audio device is NULL! Check if PySide6 QtMultimedia plugins are missing.")

        self._audio_sink = QAudioSink(target_dev, qt_format, self)
        self._audio_sink.setBufferSize(64000)  # 64KB generous ringbuffer (~2 seconds)
        self._audio_sink.setVolume(self._volume)
        self._audio_sink.stateChanged.connect(self._on_sink_state_changed)

        self._io_device = self._audio_sink.start()
        if not self._io_device:
            return False

        self._is_playing = True
        self.playback_started.emit()
        self.state_changed.emit(True)
        logging.debug(f"[AudioPlayer] Sink started: {len(self._pending_audio)} bytes buffered")

        self._write_audio_chunks()
        return True

    def append_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> bool:
        """Append raw PCM audio bytes to the stream with jitter pre-buffering.

        If not playing, buffers audio and starts sink once pre-buffer threshold is reached.
        """
        if not audio_bytes:
            return False

        self._pending_audio += audio_bytes
        self._sample_rate = sample_rate
        self._channels = channels

        logging.debug(f"[AudioPlayer] append_bytes: {len(audio_bytes)}b added, total pending={len(self._pending_audio)}b, sink_active={self._audio_sink is not None}")

        if not self._audio_sink:
            if len(self._pending_audio) >= self.BUFFER_THRESHOLD or self._stream_complete:
                return self._start_sink_and_play()
            return True

        self._write_audio_chunks()
        return True

    def _write_audio_chunks(self) -> None:
        """Push remaining audio bytes into the QAudioSink ringbuffer."""
        if not self._is_playing or not self._io_device or not self._pending_audio:
            return

        try:
            written = self._io_device.write(self._pending_audio)
            if written > 0:
                self._pending_audio = self._pending_audio[written:]

            if self._pending_audio:
                QTimer.singleShot(20, self._write_audio_chunks)
            else:
                # All pending audio has been written — check if stream is done
                logging.debug(f"[AudioPlayer] _write_audio_chunks: buffer empty, stream_complete={self._stream_complete}")
                if self._stream_complete:
                    # Poll the sink until it drains and goes idle
                    QTimer.singleShot(50, self._check_drain_complete)
        except Exception as e:
            logging.exception(f"[AudioPlayer] _write_audio_chunks error: {e}")

    def _check_drain_complete(self) -> None:
        """Periodically check if the audio sink has fully drained its hardware buffer."""
        if not self._is_playing or self._stopping:
            return
        if self._pending_audio:
            # More data arrived while we waited — abort drain check
            return
        if self._audio_sink is None:
            return

        sink_state = self._audio_sink.state()
        logging.debug(f"[AudioPlayer] _check_drain_complete: sink_state={sink_state}")
        
        # PySide6 enums can sometimes fail direct `==` comparison due to binding issues.
        # We check both the enum value and the name to be completely safe.
        is_idle = (
            sink_state == QAudio.State.IdleState 
            or getattr(sink_state, "value", -1) == getattr(QAudio.State.IdleState, "value", 3)
            or str(sink_state).endswith("IdleState")
        )
        
        if is_idle:
            logging.debug("[AudioPlayer] Sink fully drained → stopping")
            self.stop()
        else:
            # Still draining hardware buffer — check again soon
            QTimer.singleShot(30, self._check_drain_complete)

    def mark_complete(self) -> None:
        """Signal that no more audio chunks will arrive for the current stream.

        Call this after the last append_bytes() so the player knows it is safe
        to emit playback_finished once the audio sink drains.
        """
        logging.debug(
            f"[AudioPlayer] mark_complete: is_playing={self._is_playing} "
            f"pending={len(self._pending_audio)}b"
        )
        self._stream_complete = True
        if not self._audio_sink and not self._pending_audio:
            logging.debug("[AudioPlayer] mark_complete with no audio → emitting playback_finished immediately")
            self.playback_finished.emit()
            self.state_changed.emit(False)
        elif not self._audio_sink and self._pending_audio:
            self._start_sink_and_play()
        elif self._is_playing and not self._pending_audio:
            QTimer.singleShot(50, self._check_drain_complete)

    @Slot(object)
    def _on_sink_state_changed(self, state: Any) -> None:
        """Handle QAudioSink state changes — only used to detect unexpected stops."""
        logging.debug(f"[AudioPlayer] sink state changed: {state}, stream_complete={self._stream_complete}, stopping={self._stopping}")
        # We intentionally do NOT call stop() here anymore.
        # The drain is managed by _check_drain_complete() polled via QTimer.
        # This prevents false "done" triggers between TTS chunks.

    def stop(self) -> None:
        """Stop playback immediately and reset audio streams."""
        if self._stopping:
            return
        self._stopping = True

        was_playing = self._is_playing
        self._is_playing = False
        self._pending_audio = b""
        self._stream_complete = False

        if self._audio_sink:
            try:
                self._audio_sink.stateChanged.disconnect()
            except Exception:
                pass
            try:
                self._audio_sink.stop()
            except Exception:
                pass
            self._audio_sink = None
            self._io_device = None

        self._stopping = False

        if was_playing:
            logging.debug("[AudioPlayer] stop() → emitting playback_finished")
            self.playback_finished.emit()
            self.state_changed.emit(False)

    def pause(self) -> None:
        """Pause audio playback."""
        if self._audio_sink and self._is_playing:
            try:
                self._audio_sink.suspend()
            except Exception:
                pass

    def resume(self) -> None:
        """Resume paused audio playback."""
        if self._audio_sink and self._is_playing:
            try:
                self._audio_sink.resume()
            except Exception:
                pass
