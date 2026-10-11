import tempfile
import unittest
from pathlib import Path

from app.chat.chat_manager import ChatManager
from app.chat.chat_repository import ChatRepository
from app.database.database import DatabaseManager
from app.database.migrations import run_migrations
from app.models.attachment import AttachmentInput


class ChatManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "test_chat.db"
        self.database = DatabaseManager(database_path)
        self.repository = ChatRepository(self.database)
        self.manager = ChatManager(self.repository)

    def tearDown(self):
        self.database.close()
        self.temp_directory.cleanup()

    def test_migrations_are_versioned_and_idempotent(self):
        self.assertEqual(run_migrations(self.database), 3)
        self.assertEqual(run_migrations(self.database), 3)

        tables = {
            row["name"]
            for row in self.database.fetch_all(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertTrue({"schema_migrations", "conversations", "messages", "attachments"} <= tables)

    def test_attachment_history_is_persisted_and_cascades_on_chat_delete(self):
        run_migrations(self.database)
        conversation = self.manager.initialize()
        source = AttachmentInput(
            original_name="brief.pdf",
            stored_path="C:/uploads/brief.pdf",
            extension=".pdf",
            size_bytes=2048,
        )

        message = self.manager.add_user_message(
            "Summarize this", conversation.id, attachments=[source]
        )

        attachments = self.manager.get_conversation_attachments(conversation.id)
        self.assertEqual(attachments[message.id][0].original_name, "brief.pdf")
        self.assertEqual(attachments[message.id][0].size_bytes, 2048)

        self.manager.delete_chat(conversation.id)
        self.assertEqual(self.repository.list_attachments(message.id), [])

    def test_message_lifecycle_auto_titles_and_switches_chats(self):
        run_migrations(self.database)
        first_chat = self.manager.initialize()

        self.manager.add_user_message("Plan my travel itinerary", first_chat.id)
        self.manager.add_assistant_message("Where would you like to go?", first_chat.id)

        renamed_first_chat = self.manager.get_chat(first_chat.id)
        self.assertEqual(renamed_first_chat.title, "Plan my travel itinerary")
        self.assertEqual(
            [message.role for message in self.manager.get_messages(first_chat.id)],
            ["user", "assistant"],
        )

        second_chat = self.manager.create_new_chat("Work")
        self.manager.add_user_message("Prepare a release checklist", second_chat.id)
        self.manager.select_chat(first_chat.id)

        self.assertEqual(self.manager.active_conversation_id, first_chat.id)
        self.assertEqual(len(self.manager.get_messages()), 2)

    def test_api_messages_are_scoped_to_the_requested_conversation(self):
        run_migrations(self.database)
        first_chat = self.manager.initialize()
        self.manager.add_user_message("First chat question", first_chat.id)
        self.manager.add_assistant_message("First chat answer", first_chat.id)

        second_chat = self.manager.create_new_chat("Second")
        self.manager.add_user_message("Second chat question", second_chat.id)
        self.manager.add_system_message("Internal note", second_chat.id)

        self.assertEqual(
            self.manager.get_api_messages(first_chat.id),
            [
                {"role": "user", "content": "First chat question"},
                {"role": "assistant", "content": "First chat answer"},
            ],
        )
        self.assertEqual(
            self.manager.get_api_messages(second_chat.id),
            [{"role": "user", "content": "Second chat question"}],
        )

    def test_rename_search_and_delete_cascades_messages(self):
        run_migrations(self.database)
        first_chat = self.manager.initialize()
        self.manager.rename_chat(first_chat.id, "Project Alpha")
        self.manager.add_user_message("First stored message", first_chat.id)

        second_chat = self.manager.create_new_chat("Project Beta")
        self.manager.add_user_message("Second stored message", second_chat.id)

        self.assertEqual(
            [chat.title for chat in self.manager.search_chats("Project")],
            ["Project Beta", "Project Alpha"],
        )

        self.manager.delete_chat(first_chat.id)
        self.assertIsNone(self.repository.get_conversation(first_chat.id))
        self.assertEqual(self.repository.list_messages(first_chat.id), [])
        self.assertEqual(self.manager.get_active_chat().id, second_chat.id)


if __name__ == "__main__":
    unittest.main()
