import tempfile
import unittest
from pathlib import Path

from app.chat.chat_manager import ChatManager
from app.chat.chat_repository import ChatRepository
from app.database.database import DatabaseManager
from app.database.migrations import run_migrations
from app.export.business_logic import BaseExporter, ExporterRegistry, UnsupportedExportFormatError
from app.export.export_manager import ExportManager
from app.export.export_options import ExportOptions
from app.export.export_service import ExportService
from app.export.models import ExportConversation
from app.models.attachment import AttachmentInput


class RecordingExporter(BaseExporter):
    format_id = "recording"
    file_extension = ".txt"

    def __init__(self):
        self.conversation: ExportConversation | None = None

    def export(self, conversation, destination, options):
        self.conversation = conversation
        destination.write_text(conversation.title, encoding="utf-8")
        return destination


class ExportCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "test_chat.db"
        self.database = DatabaseManager(database_path)
        run_migrations(self.database)
        self.chat_manager = ChatManager(ChatRepository(self.database))
        self.chat = self.chat_manager.initialize()
        self.first_message = self.chat_manager.add_user_message(
            "প্রথম message", self.chat.id,
            attachments=[AttachmentInput("brief.pdf", "C:/uploads/brief.pdf", ".pdf", 10)],
        )
        self.chat_manager.add_assistant_message("Second message", self.chat.id)
        self.exporter = RecordingExporter()
        self.registry = ExporterRegistry([self.exporter])
        self.manager = ExportManager(ExportService(self.chat_manager, self.registry))

    def tearDown(self):
        self.database.close()
        self.temp_directory.cleanup()

    def test_registry_resolves_formats_and_rejects_duplicates_or_unknown_formats(self):
        self.assertIs(self.registry.get(".RECORDING"), self.exporter)
        with self.assertRaises(ValueError):
            self.registry.register(RecordingExporter())
        with self.assertRaises(UnsupportedExportFormatError):
            self.registry.get("pdf")

    def test_manager_exports_selected_messages_through_the_registered_exporter(self):
        destination = Path(self.temp_directory.name) / "chat.txt"

        result = self.manager.export_conversation(
            destination,
            ExportOptions("recording", message_ids=(self.first_message.id,)),
            self.chat.id,
        )

        self.assertEqual(result.destination, destination)
        self.assertEqual(result.message_count, 1)
        self.assertEqual(result.attachment_count, 1)
        self.assertEqual(self.exporter.conversation.messages[0].content, "প্রথম message")
        self.assertTrue(destination.is_file())


if __name__ == "__main__":
    unittest.main()
