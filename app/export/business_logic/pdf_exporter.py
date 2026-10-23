"""PDF conversation exporter using ReportLab presentation helpers."""

from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

from app.export.business_logic.asset_helpers import message_image_paths
from app.export.business_logic.base_exporter import BaseExporter
from app.export.business_logic.markdown_blocks import parse_markdown_blocks
from app.export.export_options import ExportOptions
from app.export.models import ExportMessage
from app.export.templates.pdf_styles import build_pdf_styles


class PdfExporter(BaseExporter):
    """Render a conversation as a polished, self-contained PDF document."""

    format_id = "pdf"
    display_name = "PDF document"
    file_extension = ".pdf"

    def export(self, conversation, destination: Path, options: ExportOptions) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        styles = build_pdf_styles()
        document = SimpleDocTemplate(
            str(destination), pagesize=letter, leftMargin=0.72 * inch,
            rightMargin=0.72 * inch, topMargin=0.72 * inch, bottomMargin=0.68 * inch,
            title=conversation.title,
        )
        story = [] if options.content_only else [Paragraph(html.escape(conversation.title), styles["title"])]
        if options.include_metadata:
            story.extend(
                Paragraph(html.escape(line), styles["meta"])
                for line in (
                    f"Conversation ID: {conversation.id}",
                    f"Created: {conversation.created_at}",
                    f"Updated: {conversation.updated_at}",
                )
            )
            story.append(Spacer(1, 5))

        for message in conversation.messages:
            story.extend(self._render_message(message, options, styles))
        document.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
        return destination

    def _render_message(self, message: ExportMessage, options: ExportOptions, styles):
        role_str = str(getattr(message.role, "value", message.role)).capitalize()
        story = [] if options.content_only else [Paragraph(role_str, styles["role"])]
        if options.include_timestamps:
            story.append(Paragraph(html.escape(str(message.created_at or "")), styles["timestamp"]))
        for block in parse_markdown_blocks(message.content):
            if block.kind == "code":
                story.append(Preformatted(block.text, styles["code"]))
            elif block.kind == "table":
                story.append(self._render_table(block.rows, styles))
            else:
                story.extend(self._render_paragraph_block(block.text, styles))

        if options.include_attachments:
            for attachment in message.attachments:
                if attachment.is_image and not options.include_images:
                    continue
                description = attachment.media_type or attachment.extension or "file"
                story.append(
                    Paragraph(
                        f"Attachment: <b>{html.escape(attachment.original_name)}</b> ({html.escape(description)})",
                        styles["attachment"],
                    )
                )
        if options.include_images:
            for image_path in message_image_paths(message):
                try:
                    image = Image(str(image_path))
                    image._restrictSize(5.6 * inch, 4.5 * inch)
                    story.extend([image, Spacer(1, 6)])
                except (OSError, ValueError):
                    story.append(Paragraph(f"Image: {html.escape(image_path.name)}", styles["attachment"]))
        return story

    @staticmethod
    def _render_paragraph_block(text: str, styles):
        story = []
        for paragraph in filter(str.strip, text.split("\n\n")):
            clean_paragraph = _remove_generated_image_markup(paragraph)
            if clean_paragraph.strip():
                story.append(Paragraph(_to_reportlab_markup(clean_paragraph), styles["body"]))
        return story

    @staticmethod
    def _render_table(rows, styles):
        table = Table(
            [[Paragraph(_to_reportlab_markup(cell), styles["body"]) for cell in row] for row in rows],
            repeatRows=1,
            hAlign="LEFT",
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF5")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C2CC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table


def _to_reportlab_markup(text: str) -> str:
    escaped = html.escape(text).replace("\n", "<br/>")
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*", r"<i>\1</i>", escaped)
    return escaped


def _remove_generated_image_markup(text: str) -> str:
    return re.sub(r"<img[^>]*>|<br\s*/?>\s*<a[^>]*>.*?</a>", "", text, flags=re.IGNORECASE | re.DOTALL)


def _draw_page_number(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawRightString(letter[0] - 0.72 * inch, 0.35 * inch, f"Page {document.page}")
    canvas.restoreState()
