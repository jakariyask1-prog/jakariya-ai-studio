"""Tests for JSON Export and ImportService."""

import json
from pathlib import Path
import pytest
from app.chat.chat_manager import ChatManager
from app.chat.chat_repository import ChatRepository
from app.export.business_logic.json_exporter import JsonExporter
from app.export.export_options import ExportOptions
from app.export.export_service import ExportService
from app.export.import_service import ImportService
from app.export.business_logic.exporter_registry import ExporterRegistry


from app.database.database import DatabaseManager
from app.database.migrations import run_migrations

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_import_export.db"
    db_mgr = DatabaseManager(db_file)
    db_mgr.initialize()
    run_migrations(db_mgr)
    repo = ChatRepository(db_mgr)
    return ChatManager(repo)


def test_json_exporter(temp_db, tmp_path):
    conversation = temp_db.create_new_chat(title="JSON Export Test")
    temp_db.add_user_message("Hello JSON Export", conversation.id)
    temp_db.add_assistant_message("Hello from AI assistant!", conversation.id)

    registry = ExporterRegistry((JsonExporter(),))
    service = ExportService(temp_db, registry)

    export_path = tmp_path / "test_chat.json"
    result = service.export_conversation(export_path, ExportOptions("json"), conversation.id)

    assert result.destination.is_file()
    assert result.message_count == 2

    with open(result.destination, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["title"] == "JSON Export Test"
    assert len(data["chat_messages"]) == 2
    assert data["chat_messages"][0]["role"] == "user"
    assert data["chat_messages"][0]["content"] == "Hello JSON Export"
    assert data["chat_messages"][1]["role"] == "assistant"
    assert data["chat_messages"][1]["content"] == "Hello from AI assistant!"


def test_import_service_roundtrip(temp_db, tmp_path):
    # Create and export
    conv1 = temp_db.create_new_chat(title="Roundtrip Chat")
    temp_db.add_user_message("What is Python?", conv1.id)
    temp_db.add_assistant_message("Python is a programming language.", conv1.id)

    registry = ExporterRegistry((JsonExporter(),))
    export_service = ExportService(temp_db, registry)
    export_path = tmp_path / "roundtrip.json"
    export_service.export_conversation(export_path, ExportOptions("json"), conv1.id)

    # Import into fresh database manager
    import_service = ImportService(temp_db)
    imported_conv = import_service.import_conversation_file(export_path)

    assert imported_conv.title == "Roundtrip Chat"
    messages = temp_db.get_messages(imported_conv.id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "What is Python?"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Python is a programming language."
