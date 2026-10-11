import unittest
from pathlib import Path
from unittest.mock import Mock

from app.chat.worker import ClaudeWorker
from app.image_generation.router import is_image_generation_request
from app.ui.chat_area import ChatArea


class ImageGenerationRoutingTests(unittest.TestCase):
    def test_natural_image_requests_are_detected(self):
        self.assertTrue(is_image_generation_request("Create a fruit image"))
        self.assertTrue(is_image_generation_request("Make me a realistic photo of a mango"))
        self.assertTrue(is_image_generation_request("Generate an image of a mountain"))
        self.assertFalse(is_image_generation_request("Explain how image generation works"))

    def test_generated_image_is_not_sent_to_claude_afterwards(self):
        worker = ClaudeWorker()
        worker.image_client = Mock()
        worker.image_client.generate.return_value = Path.cwd() / "exports" / "generated.png"
        worker.client = Mock()
        completed_messages: list[str] = []
        worker.finished.connect(completed_messages.append)

        worker.process("Create a fruit image")

        worker.image_client.generate.assert_called_once_with("Create a fruit image")
        worker.client.ask_stream.assert_not_called()
        self.assertEqual(len(completed_messages), 1)
        self.assertIn("<img src=", completed_messages[0])
        self.assertIn('width="460"', completed_messages[0])
        self.assertIn("saveimage:", completed_messages[0])

    def test_legacy_generated_image_markup_is_upgraded_for_history(self):
        legacy_message = '<img src="file:///C:/saved/image.png" width=850>'

        upgraded = ChatArea._normalise_legacy_generated_image_markup(legacy_message)

        self.assertIn('width="460"', upgraded)
        self.assertIn("saveimage:", upgraded)


if __name__ == "__main__":
    unittest.main()
