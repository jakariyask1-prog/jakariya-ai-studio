"""Application service that prepares conversations and dispatches exports."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from app.chat.chat_manager import ChatManager
from app.export.business_logic.exporter_registry import ExporterRegistry
from app.export.export_options import ExportOptions
from app.export.models import ExportConversation, ExportFormatInfo, ExportMessage, ExportResult


class ExportService:
    """Bridge persisted chat data to independent format exporters."""

    def __init__(self, chat_manager: ChatManager, registry: ExporterRegistry) -> None:
        self._chat_manager = chat_manager
        self._registry = registry

    def build_conversation_snapshot(
        self, conversation_id: str | None = None
    ) -> ExportConversation:
        """Read a complete chat once and convert it to export-domain data."""
        conversation = (
            self._chat_manager.get_chat(conversation_id)
            if conversation_id is not None
            else self._chat_manager.get_active_chat()
        )
        attachments_by_message = self._chat_manager.get_conversation_attachments(
            conversation.id
        )
        messages = (
            ExportMessage.from_message(
                message, attachments_by_message.get(message.id, ())
            )
            for message in self._chat_manager.get_messages(conversation.id)
        )
        return ExportConversation.from_conversation(conversation, messages)

    def supported_format_ids(self) -> tuple[str, ...]:
        """Return registered formats without exposing registry internals."""
        return self._registry.supported_format_ids()

    def available_formats(self) -> tuple[ExportFormatInfo, ...]:
        """Return exporter-provided labels and extensions for the UI."""
        return self._registry.available_formats()

    def export_conversation(
        self,
        destination: Path | str,
        options: ExportOptions,
        conversation_id: str | None = None,
    ) -> ExportResult:
        """Export one conversation through the exporter selected by the registry."""
        conversation = self.build_conversation_snapshot(conversation_id)
        conversation = self._apply_message_selection(conversation, options)
        exporter = self._registry.get(options.format_id)
        exported_path = exporter.export(
            conversation,
            self._destination_with_extension(destination, exporter.file_extension),
            options,
        )

        return ExportResult(
            destination=exported_path,
            format_id=options.format_id,
            message_count=len(conversation.messages),
            attachment_count=sum(
                len(message.attachments) for message in conversation.messages
            ),
        )

    def export_response(self, destination: Path | str, options: ExportOptions, title: str, content: str) -> ExportResult:
        timestamp = datetime.now().isoformat(timespec="seconds")
        conversation = ExportConversation("generated-response", title, timestamp, timestamp, (ExportMessage("generated-response", "assistant", content, timestamp),))
        exporter = self._registry.get(options.format_id)
        output = exporter.export(
            conversation,
            self._destination_with_extension(destination, exporter.file_extension),
            replace(options, include_metadata=False, include_timestamps=False, content_only=True),
        )
        return ExportResult(output, options.format_id, 1, 0)

    @staticmethod
    def _destination_with_extension(destination: Path | str, extension: str) -> Path:
        """Preserve the user's filename while adding a missing format suffix."""
        path = Path(destination)
        return path if path.suffix else path.with_suffix(extension)

    @staticmethod
    def _apply_message_selection(
        conversation: ExportConversation, options: ExportOptions
    ) -> ExportConversation:
        if options.message_ids is None:
            return conversation

        selected_ids = set(options.message_ids)
        selected_messages = tuple(
            message
            for message in conversation.messages
            if message.id in selected_ids
        )
        return replace(conversation, messages=selected_messages)
