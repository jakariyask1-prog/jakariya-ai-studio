import tempfile
import unittest
from pathlib import Path

from docx import Document
from PIL import Image
from pypdf import PdfReader

from app.chat.chat_manager import ChatManager
from app.chat.chat_repository import ChatRepository
from app.database.database import DatabaseManager
from app.database.migrations import run_migrations
from app.export import ExportOptions
from app.export.business_logic import build_default_exporter_registry
from app.export.export_manager import ExportManager
from app.export.export_service import ExportService
from app.models.attachment import AttachmentInput


class ExportIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_directory.name)
        self.database = DatabaseManager(self.workspace / "chat.db")
        run_migrations(self.database)
        self.chat_manager = ChatManager(ChatRepository(self.database))
        self.conversation = self.chat_manager.initialize()
        self.manager = ExportManager(
            ExportService(self.chat_manager, build_default_exporter_registry())
        )

        self.image_path = self.workspace / "প্রিভিউ.png"
        Image.new("RGB", (24, 16), "#357ABD").save(self.image_path)
        self.chat_manager.add_user_message(
            "বাংলা প্রশ্ন এবং একটি সংযুক্তি",
            self.conversation.id,
            attachments=(
                AttachmentInput(
                    "প্রিভিউ.png", str(self.image_path), ".png",
                    self.image_path.stat().st_size, "image/png", True,
                ),
                AttachmentInput("notes.pdf", str(self.workspace / "notes.pdf"), ".pdf", 12),
            ),
        )
        self.chat_manager.add_assistant_message(
            "## উত্তর\n\nবাংলা Unicode ঠিক থাকবে।\n\n```python\nprint('নমস্কার')\n```",
            self.conversation.id,
        )

    def tearDown(self):
        self.database.close()
        self.temp_directory.cleanup()

    def test_all_default_formats_export_a_chat_with_unicode_and_attachments(self):
        for export_format in self.manager.available_formats():
            with self.subTest(export_format=export_format.format_id):
                destination = self.workspace / f"conversation{export_format.file_extension}"
                result = self.manager.export_conversation(
                    destination, ExportOptions(export_format.format_id), self.conversation.id
                )

                self.assertEqual(result.destination, destination)
                self.assertEqual(result.message_count, 2)
                self.assertEqual(result.attachment_count, 2)
                self.assertTrue(destination.is_file())
                self.assertGreater(destination.stat().st_size, 0)

        self.assertIn("বাংলা প্রশ্ন", (self.workspace / "conversation.txt").read_text(encoding="utf-8"))
        markdown = (self.workspace / "conversation.md").read_text(encoding="utf-8")
        self.assertIn("বাংলা Unicode", markdown)
        self.assertIn("![প্রিভিউ.png](file:", markdown)
        exported_html = (self.workspace / "conversation.html").read_text(encoding="utf-8")
        self.assertIn('<meta charset="utf-8">', exported_html)
        self.assertIn("বাংলা Unicode", exported_html)
        self.assertIn("প্রিভিউ.png", exported_html)

        document = Document(self.workspace / "conversation.docx")
        self.assertIn("বাংলা প্রশ্ন", "\n".join(item.text for item in document.paragraphs))
        self.assertEqual(len(document.inline_shapes), 1)
        self.assertGreaterEqual(len(PdfReader(str(self.workspace / "conversation.pdf")).pages), 1)

    def test_missing_image_does_not_block_export(self):
        self.image_path.unlink()
        destination = self.workspace / "without-image.pdf"

        result = self.manager.export_conversation(
            destination, ExportOptions("pdf"), self.conversation.id
        )

        self.assertEqual(result.destination, destination)
        self.assertTrue(destination.is_file())

    def test_export_errors_are_propagated_to_the_ui_boundary(self):
        blocked_parent = self.workspace / "not-a-directory"
        blocked_parent.write_text("file", encoding="utf-8")

        with self.assertRaises(OSError):
            self.manager.export_conversation(
                blocked_parent / "conversation.txt", ExportOptions("txt"), self.conversation.id
            )


if __name__ == "__main__":
    unittest.main()
