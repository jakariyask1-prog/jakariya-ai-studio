from PySide6.QtCore import (
    QObject,
    QThread,
    Signal,
    Qt,
)

from collections.abc import Sequence
from typing import Any

from app.chat.worker import ChatRequest, ClaudeWorker


class ChatController(QObject):
    """
    Controls communication between the GUI and ClaudeWorker.
    """

    # Signals sent to the GUI
    thinking = Signal()
    reply_ready = Signal(str)
    partial = Signal(str)
    error = Signal(str)

    # Signal sent to the worker thread
    send_request = Signal(object)

    def __init__(self):
        super().__init__()

        # Create background thread
        self.worker_thread = QThread()

        # Create worker
        self.worker = ClaudeWorker()

        # Move worker to the background thread
        self.worker.moveToThread(self.worker_thread)

        # -----------------------------
        # Signal Connections
        # -----------------------------

        # GUI -> Worker
        self.send_request.connect(
            self.worker.process,
            Qt.ConnectionType.QueuedConnection,
        )

        # Worker -> GUI
        self.worker.started.connect(self.thinking)
        self.worker.finished.connect(self.reply_ready)
        self.worker.partial.connect(self.partial)
        self.worker.failed.connect(self.error)

        # Start worker thread
        self.worker_thread.start()

    def send_message(
        self,
        message: str | list[dict[str, Any]],
        history: Sequence[dict[str, Any]] = (),
        model: str | None = None,
        provider_id: str | None = None,
    ):
        """
        Send a message to Claude. `message` can be a plain string, or a
        list of Claude content blocks (text + image) when files are attached.
        """
        if isinstance(message, str):
            message = message.strip()
        if not message:
            return

        # Copy the selected chat's history at dispatch time.  The worker must
        # never reuse a previous conversation's in-memory history.
        self.send_request.emit(
            ChatRequest(
                message=message,
                history=tuple(dict(item) for item in history),
                model=model,
                provider_id=provider_id,
            )
        )

    def shutdown(self):
        """
        Safely stop the worker thread.
        """

        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()

            if not self.worker_thread.wait(3000):
                self.worker_thread.terminate()
                self.worker_thread.wait()

        if self.worker:
            self.worker.deleteLater()

        if self.worker_thread:
            self.worker_thread.deleteLater()

        self.worker = None
        self.worker_thread = None
