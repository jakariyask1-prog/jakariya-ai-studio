import os
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from app.ui.input_bar import InputBar
from app.chat.worker import ClaudeWorker, ChatRequest
from app.chat.chat_controller import ChatController

_APP = QApplication.instance() or QApplication([])


class CancellationFeatureTests(unittest.TestCase):

    def setUp(self):
        self.input_bar = InputBar()

    def test_initial_state_not_generating(self):
        """Input bar should start in idle state with Send icon '↑'."""
        self.assertFalse(self.input_bar.is_generating())
        self.assertEqual(self.input_bar.send_button.text(), "↑")
        self.assertTrue(self.input_bar.send_button.isEnabled())
        self.assertTrue(self.input_bar.message_input.isEnabled())

    def test_set_generating_transforms_button_to_stop(self):
        """When generating, Send button transforms into Stop button '⏹'."""
        self.input_bar.set_generating(True)
        self.assertTrue(self.input_bar.is_generating())
        self.assertEqual(self.input_bar.send_button.text(), "⏹")
        self.assertTrue(self.input_bar.send_button.isEnabled())
        self.assertFalse(self.input_bar.message_input.isEnabled())

        # When stopped, button transforms back to '↑'
        self.input_bar.set_generating(False)
        self.assertFalse(self.input_bar.is_generating())
        self.assertEqual(self.input_bar.send_button.text(), "↑")
        self.assertTrue(self.input_bar.message_input.isEnabled())

    def test_clicking_stop_button_emits_cancel_requested(self):
        """Clicking the button while generating should emit cancel_requested."""
        cancelled = []
        sent = []
        self.input_bar.cancel_requested.connect(lambda: cancelled.append(True))
        self.input_bar.send_requested.connect(sent.append)

        self.input_bar.set_generating(True)
        self.input_bar.send_button.click()

        self.assertEqual(len(cancelled), 1)
        self.assertEqual(len(sent), 0)

    def test_escape_key_in_input_box_emits_cancel_requested(self):
        """Pressing Escape key while generating emits cancel_requested."""
        cancelled = []
        self.input_bar.cancel_requested.connect(lambda: cancelled.append(True))

        self.input_bar.set_generating(True)
        esc_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        self.input_bar.message_input.keyPressEvent(esc_event)

        self.assertEqual(len(cancelled), 1)

    def test_enable_and_disable_aliases(self):
        """disable() turns on generating mode; enable() restores idle mode."""
        self.input_bar.disable()
        self.assertTrue(self.input_bar.is_generating())
        self.assertEqual(self.input_bar.send_button.text(), "⏹")

        self.input_bar.enable()
        self.assertFalse(self.input_bar.is_generating())
        self.assertEqual(self.input_bar.send_button.text(), "↑")

    def test_claude_worker_cancel_stops_streaming(self):
        """ClaudeWorker cancels active generator stream and emits cancelled signal."""
        worker = ClaudeWorker()

        chunks = ["Chunk 1", "Chunk 2", "Chunk 3", "Chunk 4"]
        mock_client = MagicMock()

        def stream_gen(*args, **kwargs):
            for c in chunks:
                if c == "Chunk 2":
                    worker.cancel()
                yield c

        mock_client.ask_stream.side_effect = stream_gen
        worker._get_client = lambda: mock_client

        received_partials = []
        cancelled_payloads = []
        finished_payloads = []

        worker.partial.connect(received_partials.append)
        worker.cancelled.connect(cancelled_payloads.append)
        worker.finished.connect(finished_payloads.append)

        req = ChatRequest(message="Hello test")
        worker.process(req)

        self.assertTrue(worker.is_cancelled())
        self.assertEqual(len(cancelled_payloads), 1)
        self.assertEqual(len(finished_payloads), 0)
        # Should have captured at least the first chunk before cancel
        self.assertIn("Chunk 1", cancelled_payloads[0])

    def test_chat_controller_cancel_delegates_to_worker(self):
        """ChatController.cancel() successfully calls worker.cancel()."""
        controller = ChatController()
        try:
            self.assertFalse(controller.worker.is_cancelled())
            controller.cancel()
            self.assertTrue(controller.worker.is_cancelled())
        finally:
            controller.shutdown()


if __name__ == "__main__":
    unittest.main()
