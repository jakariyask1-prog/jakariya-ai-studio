"""Business logic for managing the voice pipeline state.

:class:`VoiceManager` owns the active :class:`VoiceState` and coordinates
transitions between states.  It contains no Qt or UI code; it is a pure
Python orchestrator that the :class:`VoiceController` drives through
its public API.
"""

from __future__ import annotations

from app.voice.voice_service import VoiceService
from app.voice.voice_settings import VoiceSettings
from app.voice.voice_state import VoiceState


class VoiceManager:
    """Coordinate voice pipeline state while keeping UI concerns separate.

    The manager owns the current :class:`VoiceState` and delegates
    provider resolution to :class:`VoiceService`.  All state transitions
    are validated here so the controller can trust that every state change
    is legal.

    Audio capture, transcription calls, and audio playback are intentionally
    absent from this layer.  They will be added to a dedicated worker in
    a later phase.
    """

    def __init__(self, service: VoiceService) -> None:
        self._service = service
        self._state: VoiceState = VoiceState.READY
        self._live_session_active: bool = False

    @property
    def service(self) -> VoiceService:
        """Return the underlying VoiceService instance."""
        return self._service

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def state(self) -> VoiceState:
        """Return the current pipeline state."""
        return self._state

    @property
    def is_idle(self) -> bool:
        """Return ``True`` when no voice turn is in progress."""
        return self._state == VoiceState.READY

    @property
    def is_active(self) -> bool:
        """Return ``True`` when a voice turn is currently in progress."""
        return self._state not in (
            VoiceState.READY,
            VoiceState.INTERRUPTED,
            VoiceState.ERROR,
        )

    def _transition(self, new_state: VoiceState) -> None:
        """Update the internal state.

        This is the only place the state is mutated so transitions can
        be logged or validated in a single location.
        """
        self._state = new_state

    # ------------------------------------------------------------------
    # Settings pass-through
    # ------------------------------------------------------------------

    @property
    def settings(self) -> VoiceSettings:
        """Return the current voice settings from the service."""
        return self._service.settings

    def update_settings(self, settings: VoiceSettings) -> None:
        """Propagate updated settings down to the service."""
        self._service.update_settings(settings)

    # ------------------------------------------------------------------
    # Readiness
    # ------------------------------------------------------------------

    def can_start(self) -> bool:
        """Return ``True`` when a new voice turn may begin.

        Both the pipeline must be idle *and* the active providers must
        be available before a turn can start.
        """
        return self.is_idle and self._service.is_ready()

    # ------------------------------------------------------------------
    # Lifecycle hooks (called by the controller)
    # ------------------------------------------------------------------

    def on_listening_started(self) -> None:
        """Transition to LISTENING state when audio capture begins."""
        if self._state != VoiceState.LISTENING:
            self._transition(VoiceState.LISTENING)

    def on_transcribing_started(self) -> None:
        """Transition to TRANSCRIBING state when STT processing begins."""
        self._transition(VoiceState.TRANSCRIBING)

    def on_thinking_started(self) -> None:
        """Transition to THINKING state when the transcript is sent to Claude."""
        self._transition(VoiceState.THINKING)

    def on_speaking_started(self) -> None:
        """Transition to SPEAKING state when TTS playback begins."""
        self._transition(VoiceState.SPEAKING)

    def on_turn_completed(self) -> None:
        """Transition back to READY when the full voice turn has finished."""
        self._transition(VoiceState.READY)

    def on_interrupted(self) -> None:
        """Transition to INTERRUPTED when the user cancels a turn."""
        self._transition(VoiceState.INTERRUPTED)

    def on_error(self) -> None:
        """Transition to ERROR when an unrecoverable failure occurs."""
        self._transition(VoiceState.ERROR)

    def reset(self) -> None:
        """Return the pipeline to READY unconditionally.

        Called after INTERRUPTED or ERROR to allow a new voice turn.
        """
        self._transition(VoiceState.READY)

    # ------------------------------------------------------------------
    # Live Session Management
    # ------------------------------------------------------------------

    def start_live_session(self) -> None:
        """Enable continuous conversation mode."""
        self._live_session_active = True

    def stop_live_session(self) -> None:
        """Disable continuous conversation mode."""
        self._live_session_active = False

    def is_live_session_active(self) -> bool:
        """Return True when a continuous voice session is running."""
        return self._live_session_active
