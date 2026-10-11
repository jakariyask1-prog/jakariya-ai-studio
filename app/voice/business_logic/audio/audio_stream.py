"""Audio stream and chunk data structures.

Provides format specifications, audio chunk containers, and an accumulating
audio stream buffer supporting chunk-by-chunk streaming and WAV generation.
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field
from typing import Iterator

from app.voice.business_logic.audio.audio_level import AudioLevelMeter


@dataclass(frozen=True)
class AudioFormat:
    """Audio stream format parameters."""

    sample_rate: int = 16000
    channels: int = 1
    bits_per_sample: int = 16

    @property
    def bytes_per_sample(self) -> int:
        """Return the number of bytes per sample per channel."""
        return self.bits_per_sample // 8

    @property
    def bytes_per_frame(self) -> int:
        """Return the frame size in bytes (channels * bytes_per_sample)."""
        return self.channels * self.bytes_per_sample

    @property
    def byte_rate(self) -> int:
        """Return bytes per second."""
        return self.sample_rate * self.bytes_per_frame


@dataclass(frozen=True)
class AudioChunk:
    """A discrete slice of captured audio."""

    data: bytes
    timestamp: float = field(default_factory=time.time)
    duration_seconds: float = 0.0
    rms_level: float = 0.0


class AudioStream:
    """Buffer and manager for streaming or accumulated audio capture."""

    def __init__(self, audio_format: AudioFormat | None = None) -> None:
        self.format = audio_format or AudioFormat()
        self._chunks: list[AudioChunk] = []
        self._level_meter = AudioLevelMeter()

    @property
    def chunks(self) -> tuple[AudioChunk, ...]:
        """Return all accumulated audio chunks."""
        return tuple(self._chunks)

    @property
    def chunk_count(self) -> int:
        """Return the total number of chunks recorded."""
        return len(self._chunks)

    @property
    def current_level(self) -> float:
        """Return the latest smoothed RMS audio level."""
        return self._level_meter.current_level

    @property
    def total_bytes(self) -> int:
        """Return total size of accumulated raw PCM audio in bytes."""
        return sum(len(chunk.data) for chunk in self._chunks)

    @property
    def total_duration_seconds(self) -> float:
        """Return total duration of accumulated audio in seconds."""
        if self.format.byte_rate == 0:
            return 0.0
        return self.total_bytes / self.format.byte_rate

    def append(self, pcm_bytes: bytes) -> AudioChunk:
        """Append raw PCM bytes to the stream and return the created chunk."""
        duration = 0.0
        if self.format.byte_rate > 0:
            duration = len(pcm_bytes) / self.format.byte_rate

        level = self._level_meter.update(pcm_bytes)
        chunk = AudioChunk(
            data=pcm_bytes,
            timestamp=time.time(),
            duration_seconds=duration,
            rms_level=level,
        )
        self._chunks.append(chunk)
        return chunk

    def get_raw_bytes(self) -> bytes:
        """Concatenate and return all accumulated PCM bytes."""
        return b"".join(chunk.data for chunk in self._chunks)

    def get_wav_bytes(self) -> bytes:
        """Return the accumulated audio wrapped in a standard RIFF WAV header."""
        pcm_bytes = self.get_raw_bytes()
        header = self.build_wav_header(
            len(pcm_bytes),
            self.format.sample_rate,
            self.format.channels,
            self.format.bits_per_sample,
        )
        return header + pcm_bytes

    @staticmethod
    def build_wav_header(
        pcm_bytes_len: int,
        sample_rate: int = 16000,
        channels: int = 1,
        bits_per_sample: int = 16,
    ) -> bytes:
        """Generate a 44-byte RIFF WAV header for PCM audio."""
        block_align = channels * (bits_per_sample // 8)
        byte_rate = sample_rate * block_align
        chunk_size = 36 + pcm_bytes_len
        return struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            chunk_size,
            b"WAVE",
            b"fmt ",
            16,  # Subchunk1Size (16 for PCM)
            1,   # AudioFormat (1 for PCM)
            channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
            b"data",
            pcm_bytes_len,
        )

    def iter_chunks(self) -> Iterator[AudioChunk]:
        """Yield accumulated chunks sequentially for streaming."""
        yield from self._chunks

    def clear(self) -> None:
        """Clear all stored audio chunks and reset the level meter."""
        self._chunks.clear()
        self._level_meter.reset()
