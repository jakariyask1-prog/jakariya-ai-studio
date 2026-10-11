"""Voice system state machine.

Defines every state the voice pipeline can occupy.  The controller
transitions between these states as the user speaks, the STT engine
transcribes, Claude generates a reply, and the TTS engine speaks it aloud.
"""

from __future__ import annotations

from enum import Enum, auto


class VoiceState(Enum):
    """All possible states of the voice pipeline.

    Transitions follow a strict order in the happy path::

        READY → LISTENING → TRANSCRIBING → THINKING → SPEAKING → READY

    Any state may transition to INTERRUPTED (user cancelled) or ERROR
    (unrecoverable failure), both of which ultimately return to READY.
    """

    READY = auto()
    """The pipeline is idle and ready to accept a new voice turn."""

    LISTENING = auto()
    """The microphone is open and audio is being captured."""

    TRANSCRIBING = auto()
    """Captured audio is being converted to text by the STT provider."""

    THINKING = auto()
    """The transcribed text has been sent to Claude and a reply is awaited."""

    SPEAKING = auto()
    """The TTS provider is converting and playing the AI reply."""

    INTERRUPTED = auto()
    """The user cancelled an in-progress turn before it completed."""

    ERROR = auto()
    """An unrecoverable error occurred; the pipeline will reset to READY."""
