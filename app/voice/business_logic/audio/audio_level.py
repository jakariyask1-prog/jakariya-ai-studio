"""Audio level calculation and monitoring utilities.

Provides RMS (Root Mean Square) volume level calculations and smoothing
from raw 16-bit PCM audio data, designed for real-time UI level meters
and waveform visualizations.
"""

from __future__ import annotations

import math
import struct


class AudioLevelMeter:
    """Calculate and smooth RMS audio levels from raw PCM data."""

    def __init__(self, smoothing_factor: float = 0.2) -> None:
        self._smoothing_factor = max(0.0, min(1.0, smoothing_factor))
        self._current_level: float = 0.0

    @property
    def current_level(self) -> float:
        """Return the current smoothed RMS level (0.0 to 1.0)."""
        return self._current_level

    def calculate_rms(self, pcm_bytes: bytes) -> float:
        """Calculate normalized RMS level (0.0 to 1.0) for 16-bit LE PCM data."""
        if not pcm_bytes or len(pcm_bytes) < 2:
            return 0.0

        num_samples = len(pcm_bytes) // 2
        if num_samples == 0:
            return 0.0

        try:
            samples = struct.unpack(f"<{num_samples}h", pcm_bytes[: num_samples * 2])
        except struct.error:
            return 0.0

        sum_squares = sum(sample * sample for sample in samples)
        mean_square = sum_squares / num_samples
        rms = math.sqrt(mean_square)

        # Normalize against 16-bit max amplitude (32768.0)
        return min(1.0, rms / 32768.0)

    def update(self, pcm_bytes: bytes) -> float:
        """Calculate RMS for *pcm_bytes* and update the smoothed level."""
        raw_level = self.calculate_rms(pcm_bytes)
        self._current_level = (
            self._smoothing_factor * raw_level
            + (1.0 - self._smoothing_factor) * self._current_level
        )
        return self._current_level

    def reset(self) -> None:
        """Reset the smoothed audio level to 0.0."""
        self._current_level = 0.0
