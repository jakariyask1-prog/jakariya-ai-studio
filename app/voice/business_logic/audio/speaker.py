"""Speaker discovery, selection, and volume management.

Manages audio output device discovery and system volume/mute state
for the voice subsystem output layer.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtMultimedia import QMediaDevices

from app.voice.business_logic.audio.microphone import AudioDevice


class SpeakerManager(QObject):
    """Manage audio output discovery and volume/mute settings."""

    # Qt Signals for speaker state updates
    volume_changed = Signal(float)
    mute_changed = Signal(bool)
    device_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._selected_device_id: str | None = None
        self._volume: float = 1.0  # 0.0 to 1.0
        self._is_muted: bool = False

    @property
    def volume(self) -> float:
        """Return current volume level (0.0 to 1.0)."""
        return 0.0 if self._is_muted else self._volume

    @property
    def is_muted(self) -> bool:
        """Return True if speaker output is muted."""
        return self._is_muted

    @property
    def active_device_id(self) -> str | None:
        """Return selected device ID or None for OS default."""
        return self._selected_device_id

    def list_devices(self) -> list[AudioDevice]:
        """Discover available audio output devices.

        Falls back to a default Virtual Speaker device if QtMultimedia
        reports no physical output devices.
        """
        devices: list[AudioDevice] = []
        try:
            qt_outputs = QMediaDevices.audioOutputs()
            default_device = QMediaDevices.defaultAudioOutput()
            default_id = (
                bytes(default_device.id()).decode("utf-8", errors="ignore")
                if default_device
                else ""
            )

            for qt_dev in qt_outputs:
                dev_id = bytes(qt_dev.id()).decode("utf-8", errors="ignore")
                name = qt_dev.description() or "Default Speaker"
                is_def = (dev_id == default_id) or qt_dev.isDefault()
                devices.append(
                    AudioDevice(
                        device_id=dev_id,
                        name=name,
                        is_default=is_def,
                        is_input=False,
                    )
                )
        except Exception:
            pass

        if not devices:
            devices.append(
                AudioDevice(
                    device_id="default_speaker",
                    name="Default Speaker",
                    is_default=True,
                    is_input=False,
                )
            )

        return devices

    def select_device(self, device_id: str | None) -> None:
        """Select the active output device by ID."""
        self._selected_device_id = device_id
        self.device_changed.emit(device_id or "default")

    def set_volume(self, volume: float) -> None:
        """Set output volume level between 0.0 and 1.0."""
        clamped = max(0.0, min(1.0, volume))
        if self._volume != clamped:
            self._volume = clamped
            if not self._is_muted:
                self.volume_changed.emit(self._volume)

    def set_muted(self, muted: bool) -> None:
        """Mute or unmute speaker output."""
        if self._is_muted != muted:
            self._is_muted = muted
            self.mute_changed.emit(self._is_muted)
            self.volume_changed.emit(self.volume)
