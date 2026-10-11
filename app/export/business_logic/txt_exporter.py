"""Plain-text conversation exporter."""

from __future__ import annotations

from pathlib import Path

from app.export.business_logic.base_exporter import BaseExporter
from app.export.export_options import ExportOptions
from app.export.models import ExportAttachment, ExportConversation, ExportMessage


class TxtExporter(BaseExporter):
    """Write a readable, lossless text representation of a conversation."""

    format_id = "txt"
    display_name = "Plain text"
    file_extension = ".txt"

    def export(
        self,
        conversation: ExportConversation,
        destination: Path,
        options: ExportOptions,
    ) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.render(conversation, options), encoding="utf-8")
        return destination

    def render(self, conversation: ExportConversation, options: ExportOptions) -> str:
        """Render export data without performing file-system work."""
        if options.content_only:
            return "\n\n".join(message.content.rstrip() for message in conversation.messages).rstrip() + "\n"
        lines = [conversation.title, "=" * len(conversation.title), ""]
        if options.include_metadata:
            lines.extend(
                [
                    f"Conversation ID: {conversation.id}",
                    f"Created: {conversation.created_at}",
                    f"Updated: {conversation.updated_at}",
                    "",
                ]
            )

        for message in conversation.messages:
            lines.extend(self._render_message(message, options))

        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _render_message(message: ExportMessage, options: ExportOptions) -> list[str]:
        role = str(getattr(message.role, "value", message.role)).capitalize()
        heading = f"--- {role}"
        if options.include_timestamps:
            heading += f" | {message.created_at}"
        heading += " ---"

        lines = [heading, message.content.rstrip()]
        if options.include_attachments:
            lines.extend(TxtExporter._render_attachments(message.attachments, options))
        lines.append("")
        return lines

    @staticmethod
    def _render_attachments(
        attachments: tuple[ExportAttachment, ...], options: ExportOptions
    ) -> list[str]:
        lines: list[str] = []
        for attachment in attachments:
            if attachment.is_image and not options.include_images:
                continue
            lines.append(
                "Attachment: "
                f"{attachment.original_name} ({attachment.media_type or attachment.extension or 'file'})"
            )
            lines.append(f"Path: {attachment.stored_path}")
        return lines
