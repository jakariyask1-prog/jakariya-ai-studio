"""Claude-compatible JSON conversation exporter."""

from __future__ import annotations

import json
from pathlib import Path

from app.export.business_logic.base_exporter import BaseExporter
from app.export.export_options import ExportOptions
from app.export.models import ExportConversation


class JsonExporter(BaseExporter):
    """Export a conversation as structured JSON matching Claude/AI Studio schema."""

    format_id = "json"
    display_name = "JSON (Claude / AI Studio format)"
    file_extension = ".json"

    def export(
        self,
        conversation: ExportConversation,
        destination: Path,
        options: ExportOptions,
    ) -> Path:
        """Serialize conversation and messages to JSON file."""
        target = destination if destination.suffix.lower() == ".json" else destination.with_suffix(".json")

        payload = {
            "version": "1.0",
            "exporter": "Jakariya AI Studio",
            "conversation_id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "chat_messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at,
                    "attachments": [
                        {
                            "id": att.id,
                            "original_name": att.original_name,
                            "extension": att.extension,
                            "media_type": att.media_type,
                            "is_image": att.is_image,
                        }
                        for att in msg.attachments
                    ],
                }
                for msg in conversation.messages
            ],
        }

        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return target
