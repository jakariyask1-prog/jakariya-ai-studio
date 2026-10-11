"""Portable HTML conversation exporter."""

from __future__ import annotations

import html
import re
from pathlib import Path

from app.export.business_logic.asset_helpers import message_image_paths
from app.export.business_logic.base_exporter import BaseExporter
from app.export.business_logic.markdown_blocks import MarkdownBlock, parse_markdown_blocks
from app.export.export_options import ExportOptions
from app.export.models import ExportConversation, ExportMessage
from app.export.templates.html_template import render_html_document


class HtmlExporter(BaseExporter):
    """Write a readable, standalone HTML representation of a conversation."""

    format_id = "html"
    display_name = "HTML document"
    file_extension = ".html"

    def export(
        self, conversation: ExportConversation, destination: Path, options: ExportOptions
    ) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.render(conversation, options), encoding="utf-8")
        return destination

    def render(self, conversation: ExportConversation, options: ExportOptions) -> str:
        # content_only=True → pure answer blocks, no title/metadata/role wrappers
        if options.content_only:
            parts = [
                block_html
                for message in conversation.messages
                for block_html in (self._render_block(block) for block in parse_markdown_blocks(message.content))
            ]
            return render_html_document(conversation.title, "\n".join(parts))

        parts: list[str] = []
        if options.include_metadata:
            parts.append(
                '<p class="meta">'
                f"Conversation ID: {html.escape(conversation.id)}<br>"
                f"Created: {html.escape(conversation.created_at)}<br>"
                f"Updated: {html.escape(conversation.updated_at)}</p>"
            )
        for message in conversation.messages:
            parts.append(self._render_message(message, options))
        return render_html_document(conversation.title, "\n".join(parts))

    def _render_message(self, message: ExportMessage, options: ExportOptions) -> str:
        # content_only skips article wrapper and role heading — pure content only
        if options.content_only:
            blocks = [self._render_block(block) for block in parse_markdown_blocks(message.content)]
            return "\n".join(blocks)

        role_str = str(getattr(message.role, "value", message.role)).capitalize()
        parts = ["<article>", f'<div class="role">{html.escape(role_str)}</div>']
        if options.include_timestamps:
            parts.append(f'<div class="meta">{html.escape(message.created_at)}</div>')
        parts.extend(self._render_block(block) for block in parse_markdown_blocks(message.content))

        if options.include_attachments:
            attachments = [
                attachment for attachment in message.attachments
                if options.include_images or not attachment.is_image
            ]
            if attachments:
                parts.append('<ul class="attachments">')
                for attachment in attachments:
                    name = html.escape(attachment.original_name)
                    parts.append(f'<li><a href="{Path(attachment.stored_path).resolve().as_uri()}">{name}</a></li>')
                parts.append("</ul>")

        if options.include_images:
            for image_path in message_image_paths(message):
                source = html.escape(image_path.as_uri(), quote=True)
                parts.append(f'<img src="{source}" alt="{html.escape(image_path.name)}">')
        parts.append("</article>")
        return "\n".join(parts)

    @staticmethod
    def _render_block(block: MarkdownBlock) -> str:
        if block.kind == "code":
            language = html.escape(block.language)
            return f'<pre><code class="language-{language}">{html.escape(block.text)}</code></pre>'
        if block.kind == "table":
            rows = []
            for index, row in enumerate(block.rows):
                tag = "th" if index == 0 else "td"
                rows.append("<tr>" + "".join(f"<{tag}>{html.escape(cell)}</{tag}>" for cell in row) + "</tr>")
            return "<table>" + "".join(rows) + "</table>"

        lines = []
        for line in block.text.splitlines():
            if line.startswith(("# ", "## ", "### ")):
                lines.append(f"<strong>{html.escape(line.lstrip('# '))}</strong>")
            else:
                lines.append(_render_inline_markdown(line))
        return f"<p>{'<br>'.join(lines)}</p>"


def _render_inline_markdown(text: str) -> str:
    """Convert inline Markdown to safe HTML, preserving bold, italic, and code."""
    # Tokenise to avoid double-escaping inside already-processed spans.
    parts: list[str] = []
    # Pattern order matters: code first (no further processing inside), then bold, italic.
    pattern = re.compile(
        r"(\*\*(.+?)\*\*"
        r"|\*(.+?)\*"
        r"|`([^`]+)`"
        r"|~~(.+?)~~)",
        re.DOTALL,
    )
    last = 0
    for match in pattern.finditer(text):
        # Plain text before this match — escape it
        parts.append(html.escape(text[last:match.start()]))
        raw = match.group(0)
        if raw.startswith("**"):
            parts.append(f"<b>{html.escape(match.group(2))}</b>")
        elif raw.startswith("~~"):
            parts.append(f"<s>{html.escape(match.group(5))}</s>")
        elif raw.startswith("`"):
            parts.append(f"<code>{html.escape(match.group(4))}</code>")
        else:  # single *italic*
            parts.append(f"<i>{html.escape(match.group(3))}</i>")
        last = match.end()
    parts.append(html.escape(text[last:]))
    return "".join(parts)
