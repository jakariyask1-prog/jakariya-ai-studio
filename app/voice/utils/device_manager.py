"""Audio device selection and helper utilities."""

from __future__ import annotations

from app.voice.business_logic.audio.microphone import MicrophoneManager
from app.voice.business_logic.audio.speaker import SpeakerManager


class DeviceManager:
    """Helper wrapper combining microphone and speaker device discovery."""

    def __init__(
        self,
        mic_manager: MicrophoneManager | None = None,
        speaker_manager: SpeakerManager | None = None,
    ) -> None:
        self.mic_manager = mic_manager or MicrophoneManager()
        self.speaker_manager = speaker_manager or SpeakerManager()

    def get_input_devices(self):
        return self.mic_manager.list_devices()

    def get_output_devices(self):
        return self.speaker_manager.list_devices()
