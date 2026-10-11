import unittest

from app.export import ExportConversation, ExportMessage, ExportOptions
from app.models.attachment import Attachment
from app.models.conversation import Conversation
from app.models.message import Message


class ExportModelTests(unittest.TestCase):
    def test_export_snapshot_preserves_message_order_and_attachments(self):
        conversation = Conversation("chat-1", "Bangla chat", "2026-07-18T10:00:00", "2026-07-18T10:02:00")
        message = Message("message-1", "chat-1", "user", "বাংলা কোড দেখাও", "2026-07-18T10:01:00")
        attachment = Attachment(
            "file-1", "message-1", "notes.pdf", "C:/uploads/notes.pdf", ".pdf",
            128, "application/pdf", False, "2026-07-18T10:01:00",
        )

        export_message = ExportMessage.from_message(message, [attachment])
        snapshot = ExportConversation.from_conversation(conversation, [export_message])

        self.assertEqual(snapshot.messages[0].content, "বাংলা কোড দেখাও")
        self.assertEqual(snapshot.messages[0].attachments[0].original_name, "notes.pdf")
        self.assertEqual(snapshot.title, "Bangla chat")

    def test_export_options_normalize_an_extensible_format_id(self):
        options = ExportOptions(".EPUB", message_ids=(" message-1 ", "message-2"))

        self.assertEqual(options.format_id, "epub")
        self.assertEqual(options.message_ids, ("message-1", "message-2"))

    def test_export_options_reject_invalid_format_or_message_selection(self):
        with self.assertRaises(ValueError):
            ExportOptions("pdf/export")
        with self.assertRaises(ValueError):
            ExportOptions("pdf", message_ids=("",))


if __name__ == "__main__":
    unittest.main()
