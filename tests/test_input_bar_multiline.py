import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from app.ui.input_bar import InputBar, MessageInputBox


_APP = QApplication.instance() or QApplication([])


class InputBarMultilineTests(unittest.TestCase):

    def setUp(self):
        self.input_bar = InputBar()

    def test_message_input_box_multiline_initialization(self):
        self.assertIsInstance(self.input_bar.message_input, MessageInputBox)
        self.assertEqual(self.input_bar.message_input.text(), "")

    def test_text_and_set_text_compatibility(self):
        self.input_bar.message_input.setText("Hello World\nLine 2\nLine 3")
        self.assertEqual(self.input_bar.message_input.text(), "Hello World\nLine 2\nLine 3")

    def test_height_auto_adjust(self):
        initial_height = self.input_bar.message_input.height()
        # Add multiple lines
        multiline_text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6"
        self.input_bar.message_input.setText(multiline_text)
        expanded_height = self.input_bar.message_input.height()
        self.assertGreater(expanded_height, initial_height)

        # Clear text
        self.input_bar.message_input.clear()
        cleared_height = self.input_bar.message_input.height()
        self.assertLess(cleared_height, expanded_height)

    def test_send_requested_signal_on_enter(self):
        received_messages = []
        self.input_bar.send_requested.connect(received_messages.append)

        self.input_bar.message_input.setText("Testing enter key send")
        
        # Simulate pressing Enter key
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        self.input_bar.message_input.keyPressEvent(event)

        self.assertEqual(len(received_messages), 1)
        self.assertEqual(received_messages[0], "Testing enter key send")
        self.assertEqual(self.input_bar.message_input.text(), "")

    def test_shift_enter_inserts_newline(self):
        self.input_bar.message_input.setText("Line 1")
        
        # Simulate Shift+Enter
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier, "\n")
        self.input_bar.message_input.keyPressEvent(event)

        # Should NOT trigger send
        received_messages = []
        self.input_bar.send_requested.connect(received_messages.append)
        self.assertEqual(len(received_messages), 0)


if __name__ == "__main__":
    unittest.main()
