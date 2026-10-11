"""Markdown conversation exporter."""

from __future__ import annotations

from pathlib import Path

from app.export.business_logic.base_exporter import BaseExporter
from app.export.export_options import ExportOptions
from app.export.models import ExportAttachment, ExportConversation, ExportMessage


class MarkdownExporter(BaseExporter):
    """Write conversation content as portable Markdown without altering it."""

    format_id = "md"
    display_name = "Markdown"
    file_extension = ".md"

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
        """Render an export while retaining source Markdown and code blocks."""
        # content_only=True → pure answer text, no title or headers (used for per-message download)
        if options.content_only:
            return "\n\n".join(
                message.content.rstrip() for message in conversation.messages
            ).rstrip() + "\n"

        lines = [f"# {conversation.title}", ""]
        if options.include_metadata:
            lines.extend(
                [
                    f"- **Conversation ID:** `{conversation.id}`",
                    f"- **Created:** {conversation.created_at}",
                    f"- **Updated:** {conversation.updated_at}",
                    "",
                ]
            )

        for message in conversation.messages:
            lines.extend(self._render_message(message, options))

        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _render_message(message: ExportMessage, options: ExportOptions) -> list[str]:
        role_str = str(getattr(message.role, "value", message.role)).capitalize()
        heading = f"## {role_str}"
        lines = [heading]
        if options.include_timestamps:
            lines.extend([f"*{message.created_at}*", ""])
        lines.extend([message.content.rstrip(), ""])

        if options.include_attachments:
            lines.extend(MarkdownExporter._render_attachments(message.attachments, options))
        return lines

    @staticmethod
    def _render_attachments(
        attachments: tuple[ExportAttachment, ...], options: ExportOptions
    ) -> list[str]:
        visible_attachments = tuple(
            attachment
            for attachment in attachments
            if not attachment.is_image or options.include_images
        )
        if not visible_attachments:
            return []

        lines = ["### Attachments", ""]
        for attachment in visible_attachments:
            source_uri = MarkdownExporter._to_file_uri(attachment.stored_path)
            if attachment.is_image:
                lines.append(f"![{attachment.original_name}]({source_uri})")
            else:
                lines.append(f"- [{attachment.original_name}]({source_uri})")
        lines.append("")
        return lines

    @staticmethod
    def _to_file_uri(stored_path: str) -> str:
        """Produce a file URI that works even if an asset was later removed."""
        return Path(stored_path).resolve().as_uri()
