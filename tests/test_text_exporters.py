import tempfile
import unittest
from pathlib import Path

from app.export.business_logic import MarkdownExporter, TxtExporter
from app.export.export_options import ExportOptions
from app.export.models import ExportAttachment, ExportConversation, ExportMessage


class TextExporterTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.conversation = ExportConversation(
            id="chat-1",
            title="বাংলা Export Test",
            created_at="2026-07-18T10:00:00",
            updated_at="2026-07-18T10:05:00",
            messages=(
                ExportMessage(
                    id="message-1",
                    role="assistant",
                    created_at="2026-07-18T10:01:00",
                    content="Here is code:\n\n```python\nprint('hello')\n```\n\n| A | B |\n| - | - |\n| 1 | 2 |",
                    attachments=(
                        ExportAttachment(
                            id="image-1", original_name="preview.png",
                            stored_path=str(Path(self.temp_directory.name) / "preview.png"),
                            extension=".png", size_bytes=20, media_type="image/png",
                            is_image=True, created_at="2026-07-18T10:01:00",
                        ),
                        ExportAttachment(
                            id="file-1", original_name="notes.pdf",
                            stored_path=str(Path(self.temp_directory.name) / "notes.pdf"),
                            extension=".pdf", size_bytes=30, media_type="application/pdf",
                            is_image=False, created_at="2026-07-18T10:01:00",
                        ),
                    ),
                ),
            ),
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_txt_export_preserves_content_timestamps_and_attachment_references(self):
        destination = Path(self.temp_directory.name) / "nested" / "chat.txt"
        TxtExporter().export(self.conversation, destination, ExportOptions("txt"))

        text = destination.read_text(encoding="utf-8")
        self.assertIn("বাংলা Export Test", text)
        self.assertIn("2026-07-18T10:01:00", text)
        self.assertIn("```python", text)
        self.assertIn("notes.pdf", text)
        self.assertIn("preview.png", text)

    def test_markdown_export_retains_markdown_and_embeds_image_references(self):
        destination = Path(self.temp_directory.name) / "chat.md"
        MarkdownExporter().export(self.conversation, destination, ExportOptions("md"))

        text = destination.read_text(encoding="utf-8")
        self.assertIn("# বাংলা Export Test", text)
        self.assertIn("```python", text)
        self.assertIn("| A | B |", text)
        self.assertIn("![preview.png](file:", text)
        self.assertIn("[notes.pdf](file:", text)

    def test_text_exporters_honor_visibility_options(self):
        options = ExportOptions(
            "txt", include_timestamps=False, include_attachments=False, include_metadata=False
        )
        text = TxtExporter().render(self.conversation, options)

        self.assertNotIn("Conversation ID:", text)
        self.assertNotIn("2026-07-18T10:01:00", text)
        self.assertNotIn("notes.pdf", text)


if __name__ == "__main__":
    unittest.main()
