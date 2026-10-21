from __future__ import annotations

import html as html_lib
import re
import shutil
import time
from dataclasses import dataclass, field, asdict
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import quote, unquote
from typing import Optional

from PySide6.QtCore import QUrl, Qt, Signal

from app.utils.paths import get_base_dir
from PySide6.QtGui import (
    QTextCursor,
    QFont,
    QCursor,
    QDesktopServices,
    QColor,
    QBrush,
    QTextBlockFormat,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QWidget,
    QTextBrowser,
    QApplication,
    QToolTip,
    QVBoxLayout,
    QFileDialog,
)

from app.utils.markdown_renderer import render_markdown
from app.utils.creator_photos import CREATOR_PHOTO_MARKER, build_creator_photos_html
from app.utils.document_detector import DocumentDetector, DetectedDocument
from app.export.business_logic.code_exporter import code_file_type, save_code
from app.models.message import Message
from app.ui.styles import (
    CHAT_BROWSER_STYLE,
    DOCUMENT_DEFAULT_CSS,
    SYSTEM_TEXT_COLOR,
    ERROR_TEXT_COLOR,
    SMART_DOC_LIGHT_CARD_BG,
    SMART_DOC_LIGHT_CARD_BORDER,
    SMART_DOC_LIGHT_TITLE,
    SMART_DOC_LIGHT_MUTED,
    SMART_DOC_LIGHT_PREVIEW_BG,
    SMART_DOC_LIGHT_PREVIEW_BORDER,
    SMART_DOC_LIGHT_PREVIEW_TEXT,
    SMART_DOC_LIGHT_BADGE_BG,
    SMART_DOC_LIGHT_BADGE_TEXT,
    SMART_DOC_LIGHT_BADGE_BORDER,
    SMART_DOC_LIGHT_LINK,
    SMART_DOC_DARK_CARD_BG,
    SMART_DOC_DARK_CARD_BORDER,
    SMART_DOC_DARK_TITLE,
    SMART_DOC_DARK_MUTED,
    SMART_DOC_DARK_PREVIEW_BG,
    SMART_DOC_DARK_PREVIEW_BORDER,
    SMART_DOC_DARK_PREVIEW_TEXT,
    SMART_DOC_DARK_BADGE_BG,
    SMART_DOC_DARK_BADGE_TEXT,
    SMART_DOC_DARK_BADGE_BORDER,
    SMART_DOC_DARK_LINK,
)


# ============================================================
# Data model — Phase 3 (Chat History) ready
# ============================================================

@dataclass
class ChatMessage:
    """One message in the conversation.

    Plain dataclass, no Qt objects inside, so a full conversation can be
    serialized to JSON and restored later (Phase 3) without touching any
    of the rendering code below.
    """

    id: int
    role: str  # "user" | "assistant" | "system" | "error"
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class ChatArea(QWidget):
    response_export_requested = Signal(str, str)
    prompt_selected = Signal(str)
    """
    Chat conversation area: bubble UI, streaming, markdown/code rendering,
    copy actions, and a small API that Phase 3 (persistent chat history)
    can build on directly.
    """

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.chat_box = QTextBrowser()
        self.chat_box.setReadOnly(True)
        self.chat_box.setOpenLinks(False)
        self.chat_box.setOpenExternalLinks(False)
        self.chat_box.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.chat_box.anchorClicked.connect(self._on_anchor_clicked)
        font = QFont("Segoe UI Variable", 11)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        self.chat_box.setFont(font)
        self.chat_box.setStyleSheet(CHAT_BROWSER_STYLE)
        self.chat_box.document().setDefaultStyleSheet(DOCUMENT_DEFAULT_CSS)
        self.chat_box.document().setDocumentMargin(4)

        layout.addWidget(self.chat_box)

        # ---- message / history state --------------------------------
        self._messages: dict[int, ChatMessage] = {}
        self._next_message_id = 0

        # ---- code-copy state ------------------------------------------
        self._code_blocks: dict[int, object] = {}
        self._next_code_id = 0

        # ---- streaming state --------------------------------------
        self._stream_raw_text = ""
        self._stream_start_position: Optional[int] = None
        self._stream_block_start_position: Optional[int] = None
        self._stream_message_id: Optional[int] = None
        self._agent_steps: list[str] = []
        self._agent_file_paths: list[str] = []
        self._agent_live_files: dict[str, dict] = {}

        # ---- theme state -------------------------------------------
        self.theme: str = "light"

        # Render initial empty welcome state
        self.show_empty_state()

    def set_theme(self, theme: str) -> None:
        """Set the active UI theme (light, dark, oled, neon)."""
        self.theme = str(theme).lower()
        from app.ui.styles import get_chat_browser_style, get_document_css
        self.chat_box.setStyleSheet(get_chat_browser_style(self.theme))
        self.chat_box.document().setDefaultStyleSheet(get_document_css(self.theme))
        if not self._messages:
            self.show_empty_state()

    def _register_message(self, role: str, content: str) -> int:
        message_id = self._next_message_id
        self._next_message_id += 1
        self._messages[message_id] = ChatMessage(id=message_id, role=role, content=content)
        return message_id

    def _insert_block(self, html: str) -> None:
        self.chat_box.moveCursor(QTextCursor.MoveOperation.End)
        self.chat_box.insertHtml(html)
        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_box.setTextCursor(cursor)

    def _build_attachment_preview_html(self, attachments: Sequence[object]) -> str:
        """Build compact, safe previews for files stored with a message."""
        if not attachments:
            return ""

        previews: list[str] = []
        for attachment in attachments:
            name = html_lib.escape(str(getattr(attachment, "original_name", "Attachment")))
            extension = html_lib.escape(str(getattr(attachment, "extension", "")))
            is_image = bool(
                getattr(attachment, "is_image", getattr(attachment, "is_image_file", False))
            )
            stored_path = Path(str(getattr(attachment, "stored_path", "")))
            if is_image and stored_path.is_file():
                source = html_lib.escape(stored_path.resolve().as_uri(), quote=True)
                previews.append(
                    f'<div style="margin-top:4px;"><img src="{source}" alt="{name}" '
                    f'style="max-width:180px; max-height:120px; border-radius:6px;"/><br>'
                    f'<span style="font-size:9.5pt;">🖼 {name}</span></div>'
                )
            else:
                previews.append(
                    f'<span style="display:inline-block; margin-top:4px; padding:4px 8px; '
                    f'border-radius:6px; background:#EAF2FF; color:#245A9C; font-size:9.5pt;">'
                    f'📎 {name} {extension}</span>'
                )
        return "<br>".join(previews)

    def _build_user_bubble_html(self, safe_text: str, attachment_html: str = "") -> str:
        from app.ui.styles import get_theme_palette
        p = get_theme_palette(getattr(self, "theme", "light"))
        return f"""
        <table width="100%" cellspacing="0" cellpadding="0" style="margin-top:14px; margin-bottom:6px;"><tr>
            <td width="20%"></td>
            <td align="right">
                <table cellspacing="0" cellpadding="12" style="
                    background-color:{p['user_bubble']};
                    border-radius:20px 20px 4px 20px;">
                    <tr><td style="color:{p['user_text']}; font-size:11.5pt; line-height:1.5;">{safe_text}{attachment_html}</td></tr>
                </table>
            </td>
        </tr></table>
        """

    @staticmethod
    def _build_smart_document_card_html(doc: DetectedDocument, message_id: int, theme: str = "light") -> str:
        """Build a Claude Desktop-style Smart Document Card for structured documents."""
        safe_title = html_lib.escape(doc.title)
        safe_type = html_lib.escape(doc.document_type)
        safe_preview = html_lib.escape(doc.preview_text)

        is_dark = str(theme).lower() in ("dark", "oled", "neon")
        if is_dark:
            card_bg = SMART_DOC_DARK_CARD_BG
            card_border = SMART_DOC_DARK_CARD_BORDER
            title_color = SMART_DOC_DARK_TITLE
            muted_color = SMART_DOC_DARK_MUTED
            preview_bg = SMART_DOC_DARK_PREVIEW_BG
            preview_border = SMART_DOC_DARK_PREVIEW_BORDER
            preview_text = SMART_DOC_DARK_PREVIEW_TEXT
            badge_bg = SMART_DOC_DARK_BADGE_BG
            badge_color = SMART_DOC_DARK_BADGE_TEXT
            badge_border = SMART_DOC_DARK_BADGE_BORDER
            link_color = SMART_DOC_DARK_LINK
        else:
            card_bg = SMART_DOC_LIGHT_CARD_BG
            card_border = SMART_DOC_LIGHT_CARD_BORDER
            title_color = SMART_DOC_LIGHT_TITLE
            muted_color = SMART_DOC_LIGHT_MUTED
            preview_bg = SMART_DOC_LIGHT_PREVIEW_BG
            preview_border = SMART_DOC_LIGHT_PREVIEW_BORDER
            preview_text = SMART_DOC_LIGHT_PREVIEW_TEXT
            badge_bg = SMART_DOC_LIGHT_BADGE_BG
            badge_color = SMART_DOC_LIGHT_BADGE_TEXT
            badge_border = SMART_DOC_LIGHT_BADGE_BORDER
            link_color = SMART_DOC_LIGHT_LINK

        return f"""
        <table width="100%" cellspacing="0" cellpadding="0" style="margin-top:6px; margin-bottom:8px;"><tr>
            <td width="100%">
                <table width="100%" cellspacing="0" cellpadding="10" style="
                    background-color: {card_bg};
                    border: 1.2px solid {card_border};
                    border-radius: 10px;">
                    <tr><td width="100%">
                        <table width="100%" cellspacing="0" cellpadding="0"><tr>
                            <td align="left">
                                <b style="font-size:11.5pt; color:{title_color};">📄 {safe_title}</b>
                            </td>
                            <td align="right">
                                <a href="responseexport:{message_id}:pdf" style="background-color:#10A37F; color:#FFFFFF; padding:4px 10px; border-radius:6px; font-weight:700; text-decoration:none; font-size:9pt; margin-right:4px;">📄 Save PDF</a>
                                <a href="responseexport:{message_id}:docx" style="background-color:#047857; color:#FFFFFF; padding:4px 10px; border-radius:6px; font-weight:700; text-decoration:none; font-size:9pt; margin-right:6px;">📝 Save DOCX</a>
                                <span style="background-color:{badge_bg}; color:{badge_color}; border:1px solid {badge_border}; border-radius:4px; padding:3px 8px; font-weight:700; font-size:9pt;">{safe_type}</span>
                            </td>
                        </tr></table>
                        <div style="margin-top:2px; font-size:9.5pt; color:{muted_color};">
                            ~{doc.estimated_pages} page{"s" if doc.estimated_pages > 1 else ""} • {doc.word_count} words
                        </div>
                        <div style="margin-top:6px; background-color:{preview_bg}; border:1px solid {preview_border}; border-radius:6px; padding:6px 8px; font-size:10.5pt; color:{preview_text}; line-height:1.4;">
                            <i>"{safe_preview}"</i>
                        </div>
                        <div style="margin-top:8px; font-size:9.5pt; color:{muted_color};">
                            <a href="docpreview:{message_id}" style="background-color:#10A37F; color:#FFFFFF; padding:4px 10px; border-radius:5px; font-weight:600; text-decoration:none;">👁 Preview Document</a> &nbsp;
                            <a href="responseexport:{message_id}:pdf" style="color:{link_color}; font-weight:600; text-decoration:none;">📄 PDF</a> | 
                            <a href="responseexport:{message_id}:docx" style="color:{link_color}; font-weight:600; text-decoration:none;">📝 DOCX</a> | 
                            <a href="responseexport:{message_id}:xlsx" style="color:{link_color}; font-weight:600; text-decoration:none;">📊 Excel</a> | 
                            <a href="responseexport:{message_id}:md" style="color:{link_color}; font-weight:600; text-decoration:none;">⬇ MD</a> | 
                            <a href="responseexport:{message_id}:txt" style="color:{link_color}; font-weight:600; text-decoration:none;">📥 TXT</a> | 
                            <a href="messagecopy:{message_id}" style="color:{link_color}; font-weight:600; text-decoration:none;">📋 Copy</a>
                        </div>
                    </td></tr>
                </table>
            </td>
        </tr></table>
        """

    def _build_assistant_bubble_html(self, message_id: int, body_html: str, doc: Optional[DetectedDocument] = None) -> str:
        from app.ui.styles import get_theme_palette
        smart_card_html = ""
        active_theme = getattr(self, "theme", "light")
        p = get_theme_palette(active_theme)
        if doc and doc.is_document:
            smart_card_html = self._build_smart_document_card_html(doc, message_id, theme=active_theme)

        if doc and doc.is_document:
            footer_html = f"""
            <div style="margin-top:6px; font-size:9pt; color:{p['status_text']};">
                <a href="messagecopy:{message_id}" style="color:{p['status_text']}; text-decoration:none; font-weight:600;">📋 Copy Response</a>
            </div>
            """
        else:
            footer_html = f"""
            <div style="margin-top:6px; font-size:9pt; color:{p['status_text']};">
                <a href="messagecopy:{message_id}" style="color:{p['status_text']}; text-decoration:none; font-weight:600; margin-right:12px;">📋 Copy</a>
                <a href="responseexport:{message_id}:pdf" style="color:{p['status_text']}; text-decoration:none; margin-right:10px;">📄 PDF</a>
                <a href="responseexport:{message_id}:docx" style="color:{p['status_text']}; text-decoration:none; margin-right:10px;">📝 DOCX</a>
                <a href="responseexport:{message_id}:md" style="color:{p['status_text']}; text-decoration:none;">⬇ MD</a>
            </div>
            """

        return f"""
        <div style="margin-top:14px; margin-bottom:18px; width:100%;">
            {smart_card_html}
            <div style="width:100%; display:block; font-size:11.5pt; line-height:1.6; color:{p['assistant_text']};">{body_html}</div>
            {footer_html}
        </div>
        """

    @staticmethod
    def _resolve_local_file_path(path_str: str) -> str | None:
        """Resolve a candidate file path to a local existing path if possible."""
        candidate = Path(unquote(path_str).strip().strip("\"'`")).expanduser()

        if candidate.is_absolute() and candidate.exists():
            return str(candidate.resolve())

        relative_candidate = Path.cwd() / candidate
        if relative_candidate.exists():
            return str(relative_candidate.resolve())

        base_candidate = get_base_dir() / candidate
        if base_candidate.exists():
            return str(base_candidate.resolve())

        try:
            from app.agent.tools.file_tool import resolve_user_path

            user_candidate = resolve_user_path(str(candidate))
            if user_candidate.exists():
                return str(user_candidate.resolve())
        except (OSError, ValueError):
            pass

        return None

    @staticmethod
    def _extract_file_paths(text: str) -> list[str]:
        """Extract AI-generated document file paths from text."""
        file_pattern = re.compile(
            # Windows absolute path: C:\path\file.pdf or C:/path/file.pdf
            r'([a-zA-Z]:[/\\][^\s\n\*\<\>\:\"]+\.(?:pdf|docx|txt|md|html|csv|json)'
            # Relative or filename-only: word chars, dots, underscores, hyphens — NO spaces
            r'|(?:[\w][\w._-]*/)*[\w][\w._-]*\.(?:pdf|docx|txt|md|html|csv|json))',
            re.IGNORECASE
        )
        found = []
        for match in file_pattern.finditer(text):
            path_str = match.group(1).strip(".,'\"`")
            if any(path_str.lower().endswith(ext) for ext in [".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".html"]):
                if not path_str.startswith(("http", "www", "ftp")) and "://" not in path_str and len(path_str) > 4:
                    resolved_path = ChatArea._resolve_local_file_path(path_str)
                    if resolved_path and resolved_path not in found:
                        found.append(resolved_path)

        # The legacy expression above intentionally handles compact paths.
        # Add a second pass for legitimate Windows paths that contain spaces,
        # such as a OneDrive desktop or a document title with spaces.
        spaced_path_pattern = re.compile(
            r'([a-zA-Z]:[/\\][^\r\n<>"|*?]+?\.(?:pdf|docx|txt|md|html|csv|json)(?=$|[\s,;\]\)]))',
            re.IGNORECASE,
        )
        for match in spaced_path_pattern.finditer(text):
            path_str = match.group(1).strip(".,;'\"` ")
            resolved_path = ChatArea._resolve_local_file_path(path_str)
            if resolved_path and resolved_path not in found:
                found.append(resolved_path)
        return found

    def _build_file_cards_html(self, file_paths: list[str], theme: str | None = None) -> str:
        """Build Claude-style green file download card HTML for each detected file path."""
        if not file_paths:
            return ""
        active_theme = theme or getattr(self, "theme", "light")
        is_dark = str(active_theme).lower() in ("dark", "oled", "neon")
        card_bg = "#064E3B" if is_dark else "#F0FDF4"
        card_border = "#059669" if is_dark else "#22C55E"
        title_color = "#A7F3D0" if is_dark else "#15803D"
        tag_color = "#6EE7B7" if is_dark else "#166534"
        btn_save_bg = "#059669" if is_dark else "#16A34A"
        btn_open_bg = "#047857" if is_dark else "#059669"

        cards = []
        for file_path in file_paths:
            file_name = Path(file_path).name
            ext = Path(file_path).suffix.lower()
            icon = {'.pdf': '📕', '.docx': '📘', '.txt': '📝',
                    '.md': '📝', '.csv': '📊', '.json': '📊'}.get(ext, '📄')
            safe_path = quote(str(file_path))
            cards.append(
                f'<table width="100%" cellspacing="0" cellpadding="0" style="margin-top:10px; margin-bottom:6px;">'
                f'<tr><td style="background-color:{card_bg}; border:1px solid {card_border}; border-radius:10px; padding:10px 14px;">'
                f'<table width="100%" cellspacing="0" cellpadding="0"><tr>'
                f'<td align="left"><span style="font-size:15pt;">{icon}</span> '
                f'<b style="color:{title_color}; font-size:10.5pt; margin-left:6px;">{html_lib.escape(file_name)}</b>'
                f'<span style="color:{tag_color}; font-size:8.5pt; margin-left:8px;">(Ready-made Document)</span></td>'
                f'<td align="right">'
                f'<a href="savefile:{safe_path}" '
                f'style="background-color:{btn_save_bg}; color:#FFFFFF; padding:6px 14px; border-radius:6px; '
                f'text-decoration:none; font-weight:700; font-size:9.5pt; margin-right:6px;">💾 Save As...</a>'
                f'<a href="openfile:{safe_path}" '
                f'style="background-color:{btn_open_bg}; color:#FFFFFF; padding:6px 12px; border-radius:6px; '
                f'text-decoration:none; font-weight:600; font-size:9pt;">📂 Open</a>'
                f'</td>'
                f'</tr></table></td></tr></table>'
            )
        return "".join(cards)

    @classmethod
    def _render_generated_file_cards(cls, message: str) -> str:
        """Detect file paths and append file card HTML AFTER the message text (deprecated: use _extract + _build separately after render_markdown)."""
        paths = cls._extract_file_paths(message)
        cards_html = cls._build_file_cards_html(cls, paths)
        return (message + cards_html) if cards_html else message

    @staticmethod
    def _normalise_legacy_generated_image_markup(message: str) -> str:
        """Make images saved by older app versions fit and remain saveable."""
        if "saveimage:" in message:
            return message

        image_pattern = re.compile(
            r'<img\s+[^>]*\bsrc=["\'](file://[^"\']+)["\'][^>]*>', re.IGNORECASE
        )

        def replace_image(match: re.Match[str]) -> str:
            source_uri = match.group(1)
            source_path = QUrl(source_uri).toLocalFile()
            if not source_path:
                return match.group(0)
            save_target = quote(str(Path(source_path)))
            return (
                '<div style="text-align:center; margin:8px 0;">'
                f'<img src="{source_uri}" width="460">'
                f'<br><a href="saveimage:{save_target}">💾 Save image</a></div>'
            )

        return image_pattern.sub(replace_image, message)

    def _typing_block_format(self) -> QTextBlockFormat:
        from app.ui.styles import get_theme_palette
        p = get_theme_palette(getattr(self, "theme", "light"))
        fmt = QTextBlockFormat()
        fmt.setBackground(QBrush(QColor(p["assistant_bubble"])))
        fmt.setLeftMargin(8)
        fmt.setRightMargin(12)
        fmt.setTopMargin(8)
        fmt.setBottomMargin(4)
        return fmt

    # =============================================================
    # Public API — User message
    # =============================================================

    def append_user_message(self, message: str, attachments: Sequence[object] = ()) -> int:
        """Render a right-aligned user bubble. Returns the message id."""
        message_id = self._register_message("user", message)
        safe = html_lib.escape(message).replace("\n", "<br>")
        self._insert_block(
            self._build_user_bubble_html(safe, self._build_attachment_preview_html(attachments))
        )
        self.scroll_to_bottom()
        return message_id

    # =============================================================
    # Public API — Assistant message (non-streaming / already complete)
    # =============================================================

    def append_assistant_message(self, message: str) -> int:
        message_id = self._register_message("assistant", message)
        display_message = self._normalise_legacy_generated_image_markup(message)

        # Detect Document
        doc = DocumentDetector.detect(display_message)

        # Extract file paths BEFORE markdown rendering so they survive HTML escaping
        file_paths = self._extract_file_paths(display_message)

        # Check for creator photo marker and strip it from the rendered text
        creator_photos_html = ""
        if CREATOR_PHOTO_MARKER in display_message:
            creator_photos_html = build_creator_photos_html(getattr(self, "theme", "light"))
            display_message = display_message.replace(CREATOR_PHOTO_MARKER, "").strip()

        rendered_html, code_map, self._next_code_id = render_markdown(
            display_message, self._next_code_id, theme=getattr(self, "theme", "light")
        )
        self._code_blocks.update(code_map)

        # Append file cards and creator photos AFTER markdown rendering
        file_cards_html = self._build_file_cards_html(file_paths)
        final_body_html = creator_photos_html + rendered_html + file_cards_html

        self._insert_block(self._build_assistant_bubble_html(message_id, final_body_html, doc=doc))
        self.scroll_to_bottom()
        return message_id

    # =============================================================
    # Public API — Assistant streaming
    # =============================================================

    def start_assistant_stream(self) -> int:
        """Open a lightweight "typing" bubble and return its message id."""
        message_id = self._next_message_id
        self._next_message_id += 1
        self._stream_message_id = message_id

        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._stream_block_start_position = cursor.position()

        block_fmt = self._typing_block_format()
        cursor.insertBlock(block_fmt)

        bold_fmt = QTextCharFormat()
        bold_fmt.setFontWeight(QFont.Bold)
        cursor.insertText("Jakariya AI Studio", bold_fmt)
        cursor.insertText("   ✍️ typing…", QTextCharFormat())

        # New block for the streamed body text (same background, so it
        # reads as one continuous bubble while typing).
        cursor.insertBlock(block_fmt)
        self.chat_box.setTextCursor(cursor)

        self._stream_raw_text = ""
        self._stream_start_position = cursor.position()

        self.scroll_to_bottom()
        return message_id

    def append_assistant_stream(self, chunk: str) -> None:
        if not chunk:
            return

        self._stream_raw_text += chunk

        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.chat_box.setTextCursor(cursor)

        self.scroll_to_bottom()

    def end_assistant_stream(self, final_message: str | None = None) -> None:
        if final_message is not None and not self._stream_raw_text:
            self._stream_raw_text = final_message

        if self._stream_block_start_position is not None:
            # Wipe out the transient "typing" block (header + plain text)
            # in one go...
            cursor = self.chat_box.textCursor()
            cursor.setPosition(
                self._stream_block_start_position,
                QTextCursor.MoveMode.MoveAnchor,
            )
            cursor.movePosition(
                QTextCursor.MoveOperation.End,
                QTextCursor.MoveMode.KeepAnchor,
            )
            cursor.removeSelectedText()
            cursor.setBlockFormat(QTextBlockFormat())  # clear leftover background

            message_id = self._stream_message_id
            if message_id is None:
                message_id = self._next_message_id
                self._next_message_id += 1

            self._messages[message_id] = ChatMessage(
                id=message_id, role="assistant", content=self._stream_raw_text
            )

            raw_for_render = self._normalise_legacy_generated_image_markup(self._stream_raw_text)
            doc = DocumentDetector.detect(raw_for_render)
            file_paths = self._extract_file_paths(raw_for_render)

            # Check for creator photo marker and strip it from the rendered text
            stream_creator_photos_html = ""
            if CREATOR_PHOTO_MARKER in raw_for_render:
                stream_creator_photos_html = build_creator_photos_html(getattr(self, "theme", "light"))
                raw_for_render = raw_for_render.replace(CREATOR_PHOTO_MARKER, "").strip()

            rendered_html, code_map, self._next_code_id = render_markdown(
                raw_for_render,
                self._next_code_id,
                theme=getattr(self, "theme", "light"),
            )
            self._code_blocks.update(code_map)

            file_cards_html = self._build_file_cards_html(file_paths)
            final_body_html = stream_creator_photos_html + rendered_html + file_cards_html

            cursor.insertHtml(
                self._build_assistant_bubble_html(message_id, final_body_html, doc=doc)
            )
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.chat_box.setTextCursor(cursor)
        elif final_message is not None:
            self.append_assistant_message(final_message)
        else:
            cursor = self.chat_box.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.chat_box.setTextCursor(cursor)

        self._stream_raw_text = ""
        self._stream_start_position = None
        self._stream_block_start_position = None
        self._stream_message_id = None

        self.scroll_to_bottom()

    def cancel_assistant_stream(self) -> None:
        """Remove an unfinished streaming bubble without adding it to history."""
        if self._stream_block_start_position is not None:
            cursor = self.chat_box.textCursor()
            cursor.setPosition(
                self._stream_block_start_position,
                QTextCursor.MoveMode.MoveAnchor,
            )
            cursor.movePosition(
                QTextCursor.MoveOperation.End,
                QTextCursor.MoveMode.KeepAnchor,
            )
            cursor.removeSelectedText()
            cursor.setBlockFormat(QTextBlockFormat())
            self.chat_box.setTextCursor(cursor)

        self._stream_raw_text = ""
        self._stream_start_position = None
        self._stream_block_start_position = None
        self._stream_message_id = None
        self._agent_steps.clear()

    # =============================================================
    # Public API — Agent Working Bubble Chat
    # =============================================================

    def start_agent_bubble(self) -> int:
        """Start rendering an active, dynamic agent working bubble in the chat."""
        message_id = self._next_message_id
        self._next_message_id += 1
        self._stream_message_id = message_id
        self._agent_steps.clear()
        self._agent_live_files.clear()
        self._stream_raw_text = ""

        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._stream_block_start_position = cursor.position()

        initial_html = """
        <table width="100%" cellspacing="0" cellpadding="0" style="margin-top:8px;"><tr>
            <td width="100%">
                <table width="100%" cellspacing="0" cellpadding="12" style="
                    background-color: #F8FAFC;
                    border: 1px solid #6366F1;
                    border-radius: 14px;">
                    <tr><td width="100%">
                        <div style="margin-bottom:8px;">
                            <span style="background-color:#EEF2FF; color:#4F46E5; border:1px solid #C7D2FE; border-radius:6px; padding:3px 10px; font-weight:700; font-size:10pt;">ReAct Agent</span>
                            <b style="color:#0F172A; font-size:11pt; margin-left:6px;">Executing Task...</b>
                        </div>
                        <div id="agent_steps" style="font-size:9.5pt; color:#334155; line-height:1.4;">
                            • 🧠 Initializing task execution plan...
                        </div>
                    </td></tr>
                </table>
            </td>
        </tr></table>
        <br>
        """
        cursor.insertHtml(initial_html)
        self.chat_box.setTextCursor(cursor)
        self.scroll_to_bottom()
        return message_id

    def update_agent_progress(self, message: str, tool_name: str = "", is_tool: bool = False) -> None:
        """Update the agent working bubble with real-time steps, tool badges, and explicit error callouts."""
        if not message.strip():
            return

        active_theme = getattr(self, "theme", "light")
        is_dark = str(active_theme).lower() in ("dark", "oled", "neon")
        card_bg = "#1E293B" if is_dark else "#F8FAFC"
        title_color = "#F8FAFC" if is_dark else "#0F172A"
        step_color = "#E2E8F0" if is_dark else "#334155"
        thought_color = "#818CF8" if is_dark else "#4F46E5"
        tool_badge_bg = "#312E81" if is_dark else "#EEF2FF"
        tool_badge_fg = "#C7D2FE" if is_dark else "#3730A3"
        tool_badge_border = "#4338CA" if is_dark else "#C7D2FE"

        safe_msg = html_lib.escape(message.strip())
        if "Error" in safe_msg or "Exception" in safe_msg or "declined" in safe_msg or "failed" in safe_msg.lower():
            clean_err = safe_msg.replace("Observation: Error -", "").replace("Observation:", "").strip()
            step_item = (
                f'• <span style="background-color:#FEE2E2; color:#DC2626; border:1px solid #FCA5A5; '
                f'border-radius:6px; padding:2px 6px; font-weight:700; font-size:8.5pt;">❌ Failed</span> '
                f'<span style="color:#B91C1C; font-weight:600;">Reason: {clean_err}</span>'
            )
        elif is_tool or tool_name:
            badge_name = html_lib.escape(tool_name if tool_name else "tool")
            display_msg = safe_msg

            # Format Antigravity diff statistics (+added / -removed) and folders
            import re
            diff_match = re.search(r"\(\+([0-9]+)(?:\s*/\s*-([0-9]+))?\s*lines", safe_msg)
            folder_match = re.search(r"in &#x27;([^&#]+)&#x27;|in '([^']+)'", safe_msg)
            file_match = re.search(r"[`'\"]([a-zA-Z0-9_.\-/\\]+\.[a-zA-Z0-9]+)[`'\"]", safe_msg)

            diff_badges = ""
            if diff_match:
                added = diff_match.group(1)
                removed = diff_match.group(2)
                if added and added != "0":
                    diff_badges += f'<span style="background-color:#DCFCE7; color:#15803D; border:1px solid #86EFAC; border-radius:4px; padding:1px 6px; font-weight:700; font-size:8.5pt;">+{added}</span> '
                if removed and removed != "0":
                    diff_badges += f'<span style="background-color:#FEE2E2; color:#DC2626; border:1px solid #FCA5A5; border-radius:4px; padding:1px 6px; font-weight:700; font-size:8.5pt;">-{removed}</span> '

            folder_badge = ""
            if folder_match:
                fldr = folder_match.group(1) or folder_match.group(2)
                folder_badge = f'<span style="background-color:#F1F5F9; color:#475569; border:1px solid #CBD5E1; border-radius:4px; padding:1px 6px; font-weight:500; font-size:8.5pt;">📁 {fldr}</span> '

            # Register live file for real-time Antigravity live file changes card
            if file_match and (diff_match or tool_name in ("edit_file", "write_file")):
                raw_fn = file_match.group(1).replace("\\", "/")
                fn = Path(raw_fn).name
                fld = folder_match.group(1) or folder_match.group(2) if folder_match else (Path(raw_fn).parent.name or "workspace")
                add_lines = int(diff_match.group(1)) if (diff_match and diff_match.group(1)) else 0
                rem_lines = int(diff_match.group(2)) if (diff_match and diff_match.group(2)) else 0
                act_name = "created" if ("created" in safe_msg.lower() or tool_name == "write_file") else "modified"
                self._agent_live_files[fn] = {
                    "file_name": fn,
                    "folder": fld,
                    "lines_added": add_lines,
                    "lines_removed": rem_lines,
                    "action": act_name,
                }

            extra_badges = f"{folder_badge}{diff_badges}".strip()
            if tool_name == "review_diffs":
                extra_badges += ' <a href="reviewchanges:latest" style="background-color:#10A37F; color:#FFFFFF; border-radius:4px; padding:2px 8px; text-decoration:none; font-weight:700; font-size:8.5pt; margin-left:6px;">👁️ Review Changes</a>'
            elif tool_name in ("view_file", "read_file"):
                extra_badges += ' <span style="color:#10A37F; font-size:8.5pt; font-weight:600; margin-left:4px;">(Read Only)</span>'

            extra_badges_str = f" {extra_badges.strip()}" if extra_badges.strip() else ""
            step_item = (
                f'• <span style="background-color:{tool_badge_bg}; color:{tool_badge_fg}; border:1px solid {tool_badge_border}; '
                f'border-radius:6px; padding:2px 6px; font-weight:700; font-size:8.5pt;">🛠 Tool: {badge_name}</span>'
                f'{extra_badges_str} <span style="color:{step_color};">{display_msg}</span>'
            )
        elif "Thought:" in safe_msg:
            step_item = f'• <span style="color:{thought_color}; font-weight:600;">🧠 {safe_msg}</span>'
        else:
            step_item = f'• <span style="color:{step_color};">{safe_msg}</span>'

        self._agent_steps.append(step_item)

        if self._stream_block_start_position is not None:
            cursor = self.chat_box.textCursor()
            cursor.setPosition(self._stream_block_start_position, QTextCursor.MoveMode.MoveAnchor)
            cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.setBlockFormat(QTextBlockFormat())

            steps_html = "<br>".join(self._agent_steps)  # Show ALL steps live

            # Build Live Files Modified panel (Antigravity Live Tracker)
            live_files_html = ""
            if self._agent_live_files:
                file_items = []
                for fn, info in self._agent_live_files.items():
                    fld_name = info["folder"]
                    add_n = info["lines_added"]
                    rem_n = info["lines_removed"]
                    diff_str = ""
                    if add_n:
                        diff_str += f'<span style="background-color:#DCFCE7; color:#15803D; border:1px solid #86EFAC; border-radius:4px; padding:1px 5px; font-weight:700; font-size:8pt;">+{add_n}</span> '
                    if rem_n:
                        diff_str += f'<span style="background-color:#FEE2E2; color:#DC2626; border:1px solid #FCA5A5; border-radius:4px; padding:1px 5px; font-weight:700; font-size:8pt;">-{rem_n}</span> '
                    act_badge = f'<span style="background-color:{"#312E81" if is_dark else "#EEF2FF"}; color:{"#C7D2FE" if is_dark else "#4F46E5"}; border-radius:4px; padding:1px 5px; font-weight:600; font-size:8pt;">{info["action"].capitalize()}</span>'
                    file_items.append(
                        f'<div style="margin:2px 4px 2px 0; display:inline-block; '
                        f'background:{"#0F172A" if is_dark else "#FFFFFF"}; border:1px solid {"#334155" if is_dark else "#CBD5E1"}; '
                        f'border-radius:6px; padding:3px 8px; font-size:8.5pt;">'
                        f'📄 <b>{html_lib.escape(fn)}</b> <span style="color:#64748B;">({html_lib.escape(fld_name)})</span> {diff_str}{act_badge}'
                        f'</div>'
                    )
                live_files_joined = "".join(file_items)
                live_files_html = f"""
                <div style="background-color:{"#0F172A" if is_dark else "#F1F5F9"}; border:1px solid {"#334155" if is_dark else "#CBD5E1"}; border-radius:8px; padding:8px 10px; margin-top:6px; margin-bottom:10px;">
                    <div style="font-weight:700; color:{"#818CF8" if is_dark else "#4F46E5"}; font-size:9.5pt; margin-bottom:4px;">
                        📝 Live Files Modified ({len(self._agent_live_files)}) (Antigravity Tracker):
                    </div>
                    <div>{live_files_joined}</div>
                </div>
                """

            updated_card = f"""
            <table width="100%" cellspacing="0" cellpadding="0" style="margin-top:8px;"><tr>
                <td width="100%">
                    <table width="100%" cellspacing="0" cellpadding="12" style="
                        background-color: {card_bg};
                        border: 1px solid #6366F1;
                        border-radius: 14px;">
                        <tr><td width="100%">
                            <div style="margin-bottom:8px;">
                                <span style="background-color:{tool_badge_bg}; color:{tool_badge_fg}; border:1px solid {tool_badge_border}; border-radius:6px; padding:3px 10px; font-weight:700; font-size:10pt;">ReAct Agent</span>
                                <b style="color:{title_color}; font-size:11pt; margin-left:6px;">Executing Task...</b>
                            </div>
                            {live_files_html}
                            <div style="font-size:9.5pt; color:{step_color}; line-height:1.4;">
                                {steps_html}
                            </div>
                        </td></tr>
                    </table>
                </td>
            </tr></table>
            <br>
            """
            cursor.insertHtml(updated_card)
            self.chat_box.setTextCursor(cursor)

        self.scroll_to_bottom()

    def end_agent_bubble(self, final_message: str | None = None) -> None:
        """Replace working agent bubble with final answer response while preserving step-by-step log and tool errors."""

        raw_output = final_message or ""
        active_theme = getattr(self, "theme", "light")
        is_dark = str(active_theme).lower() in ("dark", "oled", "neon")

        timeline_bg = "#1E293B" if is_dark else "#F1F5F9"
        timeline_border = "#334155" if is_dark else "#CBD5E1"
        timeline_header = "#94A3B8" if is_dark else "#475569"
        timeline_text = "#E2E8F0" if is_dark else "#334155"

        err_bg = "#450A0A" if is_dark else "#FEF2F2"
        err_title = "#F87171" if is_dark else "#DC2626"
        err_text = "#FCA5A5" if is_dark else "#991B1B"

        # --- 1. Build the persistent step execution log ---
        steps_summary_html = ""
        if self._agent_steps:
            steps_joined = "<br>".join(self._agent_steps)
            steps_summary_html = (
                f'<div style="background-color:{timeline_bg}; border:1px solid {timeline_border}; '
                f'border-radius:8px; padding:10px; margin-bottom:12px; font-size:9.5pt;">'
                f'<div style="font-weight:700; color:{timeline_header}; margin-bottom:6px;">'
                f'⚡ Agent Execution Timeline ({len(self._agent_steps)} steps):</div>'
                f'<div style="color:{timeline_text}; line-height:1.5;">{steps_joined}</div>'
                f'</div>'
            )
        self._agent_steps.clear()

        # --- 2. Check for explicit Tool Errors and build Error Callout ---
        error_callout_html = ""
        if "Observation: Error" in raw_output or "Observation: Exception" in raw_output or "declined by user permission policy" in raw_output:
            err_line = ""
            for line in raw_output.split("\n"):
                if line.strip().startswith(("Observation: Error", "Observation: Exception")) or "declined" in line:
                    err_line = line.strip()
                    break
            clean_reason = html_lib.escape(err_line.replace("Observation: Error -", "").replace("Observation: Exception running tool", "").strip())
            error_callout_html = (
                f'<div style="background-color:{err_bg}; border:1.5px solid #EF4444; border-radius:10px; '
                f'padding:12px 14px; margin-top:10px; margin-bottom:10px;">'
                f'<b style="color:{err_title}; font-size:10.5pt;">❌ Failed</b><br>'
                f'<span style="color:{err_text}; font-size:10pt; font-weight:600;">Reason: {clean_reason}</span>'
                f'</div>'
            )

        # --- 2b. Check for Task Cancellation ---
        cancelled_callout_html = ""
        if "Task Cancelled" in raw_output:
            cancel_bg = "#334155" if is_dark else "#F1F5F9"
            cancel_fg = "#CBD5E1" if is_dark else "#475569"
            cancel_border = "#475569" if is_dark else "#CBD5E1"
            cancelled_callout_html = (
                f'<div style="background-color:{cancel_bg}; border:1px solid {cancel_border}; border-radius:8px; '
                f'padding:10px 12px; margin-top:8px; margin-bottom:8px;">'
                f'<span style="font-weight:700; color:{cancel_fg}; font-size:9.5pt;">⏹ Task was stopped by user.</span>'
                f'</div>'
            )

        # --- 3. Extract clean final answer from raw ReAct output ---
        clean_text = raw_output
        if "Task Cancelled" in clean_text:
            clean_text = "*(Task stopped by user)*"
        elif "Final Answer:" in clean_text:
            clean_text = clean_text.split("Final Answer:", 1)[1].strip()
        elif "Observation: Error" in clean_text or "Observation: Exception" in clean_text:
            lines = []
            for line in clean_text.split("\n"):
                stripped = line.strip()
                if not stripped.startswith(("Thought:", "Action:", "Action Input:", "Observation:")) and not stripped.startswith("```"):
                    lines.append(line)
            clean_text = "\n".join(lines).strip()

        if not clean_text and error_callout_html:
            clean_text = "Tool execution encountered an error."

        self._agent_file_paths = self._extract_file_paths(clean_text)
        doc = DocumentDetector.detect(clean_text)

        message_id = self._stream_message_id
        if message_id is None:
            message_id = self._next_message_id
            self._next_message_id += 1

        self._messages[message_id] = ChatMessage(
            id=message_id, role="assistant", content=clean_text
        )

        rendered_md, code_map, self._next_code_id = render_markdown(
            clean_text, self._next_code_id, theme=active_theme
        )
        self._code_blocks.update(code_map)

        file_cards_html = self._build_file_cards_html(self._agent_file_paths)

        full_body_html = steps_summary_html + error_callout_html + cancelled_callout_html + rendered_md + file_cards_html

        if self._stream_block_start_position is not None:
            cursor = self.chat_box.textCursor()
            cursor.setPosition(self._stream_block_start_position, QTextCursor.MoveMode.MoveAnchor)
            cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.setBlockFormat(QTextBlockFormat())
            cursor.insertHtml(self._build_assistant_bubble_html(message_id, full_body_html, doc=doc))
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.chat_box.setTextCursor(cursor)
        else:
            self._insert_block(self._build_assistant_bubble_html(message_id, full_body_html, doc=doc))

        # Reset streaming state
        self._stream_raw_text = ""
        self._stream_start_position = None
        self._stream_block_start_position = None
        self._stream_message_id = None
        self.scroll_to_bottom()

    # =============================================================
    # Copy actions (Phase 2.4)
    # =============================================================

    def _on_anchor_clicked(self, url: QUrl) -> None:
        url_str = url.toString()

        if url_str.startswith("docpreview:"):
            try:
                message_id = int(url_str.split(":", 1)[1])
                msg = self._messages.get(message_id)
                if msg and msg.content:
                    doc = DocumentDetector.detect(msg.content)
                    from app.ui.document_preview_dialog import DocumentPreviewDialog
                    dialog = DocumentPreviewDialog(
                        title=doc.title,
                        document_type=doc.document_type,
                        word_count=doc.word_count,
                        estimated_pages=doc.estimated_pages,
                        raw_content=doc.raw_content,
                        parent=self.window(),
                    )
                    dialog.exec()
            except Exception as exc:
                print(f"[ChatArea] Document preview error: {exc}")
            return

        if url_str.startswith("promptcard:"):
            prompt_text = unquote(url_str.split(":", 1)[1])
            self.prompt_selected.emit(prompt_text)
            return

        if url_str.startswith("reviewchanges:"):
            try:
                from app.agent.diff_tracker import DiffTracker
                from app.ui.code_changes_review_dialog import CodeChangesReviewDialog
                param = url_str.split(":", 1)[1] if ":" in url_str else "latest"
                parts = param.split(":", 1)
                session_id = parts[0] if parts[0] else "latest"
                initial_file = parts[1] if len(parts) > 1 else ""
                changes = DiffTracker.instance().get_changes(session_id)
                dialog = CodeChangesReviewDialog(
                    changes=changes,
                    parent=self.window(),
                    theme=getattr(self, "theme", "light"),
                    initial_file=initial_file,
                )
                dialog.exec()
            except Exception as exc:
                print(f"[ChatArea] Code changes review error: {exc}")
            return

        if url_str.startswith("openfile:"):
            target_path = Path(unquote(url_str.split(":", 1)[1]))
            abs_target = target_path if target_path.is_absolute() else Path.cwd() / target_path
            abs_target = abs_target.resolve()

            if not abs_target.exists() and not target_path.is_absolute():
                fallback = get_base_dir() / target_path
                if fallback.exists():
                    abs_target = fallback.resolve()

            if abs_target.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(abs_target)))
                QToolTip.showText(QCursor.pos(), f"📂 Opened file: {abs_target.name}", self.chat_box)
            else:
                QToolTip.showText(
                    QCursor.pos(),
                    f"⚠️ File not found locally:\n{target_path.name}",
                    self.chat_box
                )
            return

        if url_str.startswith("savefile:"):
            target_path = Path(unquote(url_str.split(":", 1)[1]))
            abs_target = target_path if target_path.is_absolute() else Path.cwd() / target_path
            abs_target = abs_target.resolve()

            if not abs_target.exists() and not target_path.is_absolute():
                fallback = get_base_dir() / target_path
                if fallback.exists():
                    abs_target = fallback.resolve()

            if not abs_target.exists():
                QToolTip.showText(
                    QCursor.pos(),
                    f"⚠️ File not found locally:\n{target_path.name}",
                    self.chat_box
                )
                return

            ext = abs_target.suffix.lower()
            file_filter = f"{ext.upper().strip('.')} Files (*{ext});;All Files (*.*)"
            destination, _ = QFileDialog.getSaveFileName(
                self,
                "Save File As...",
                abs_target.name,
                file_filter,
            )
            if not destination:
                return

            destination_path = Path(destination)
            if not destination_path.suffix:
                destination_path = destination_path.with_suffix(ext)

            try:
                shutil.copy2(str(abs_target), destination_path)
                dest_path = destination_path
                QToolTip.showText(QCursor.pos(), f"✅ Saved file to: {dest_path.name}", self.chat_box)
            except Exception as exc:
                QToolTip.showText(QCursor.pos(), f"⚠️ Could not save file: {exc}", self.chat_box)
            return

        if url_str.startswith("saveimage:"):
            source_path = Path(unquote(url_str.split(":", 1)[1]))
            self._save_generated_image(source_path)
            return

        # Copy entire assistant response
        if url_str.startswith("messagecopy:"):
            try:
                message_id = int(url_str.split(":", 1)[1])
            except ValueError:
                return

            msg = self._messages.get(message_id)
            if msg is None:
                return

            QApplication.clipboard().setText(msg.content)
            QToolTip.showText(QCursor.pos(), "✅ Response Copied!", self.chat_box)
            return

        # Copy a single code block
        if url_str.startswith("responseexport:"):
            try:
                _, message_id_text, format_id = url_str.split(":", 2)
                message = self._messages.get(int(message_id_text))
            except (TypeError, ValueError):
                return
            if message is not None and message.role == "assistant":
                # If the user has explicitly highlighted a body paragraph, export that portion.
                # Otherwise ignore accidental link selection text ("Download PDF", "Download MD", "Download HTML", etc.) and export full response.
                selected_text = self.chat_box.textCursor().selectedText().strip()
                if selected_text and not any(kw in selected_text.lower() for kw in ["download", "txt", "md", "html", "pdf", "docx", "📥"]) and len(selected_text) > 20:
                    content_to_export = selected_text
                else:
                    content_to_export = message.content
                self.response_export_requested.emit(format_id, content_to_export)
            return


        if url_str.startswith("copy:"):
            try:
                block_id = int(url_str.split(":", 1)[1])
            except ValueError:
                return

            code = self._code_blocks.get(block_id)
            if code is None:
                return

            QApplication.clipboard().setText(code.content)
            QToolTip.showText(QCursor.pos(), "✅ Copied!", self.chat_box)
            return

        if url_str.startswith("codedownload:"):
            try:
                block_id = int(url_str.split(":", 1)[1])
            except ValueError:
                return

            code = self._code_blocks.get(block_id)
            if code is None:
                return

            self._save_code_block(code.content, code.language)
            return

        QDesktopServices.openUrl(url)

    def _save_code_block(self, content: str, language: str) -> None:
        """Save an AI-generated code block using its fenced-code language."""
        file_type = code_file_type(language)
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Save code block",
            f"generated_code{file_type.extension}",
            file_type.file_filter,
        )
        if not destination:
            return

        try:
            saved_path = save_code(content, destination, file_type)
        except OSError as error:
            QToolTip.showText(QCursor.pos(), f"Could not save code: {error}", self.chat_box)
            return

        QToolTip.showText(QCursor.pos(), f"Code saved: {saved_path.name}", self.chat_box)

    def _save_generated_image(self, source_path: Path) -> None:
        """Copy a generated image to a user-selected download location."""
        if not source_path.is_file():
            QToolTip.showText(QCursor.pos(), "Image file is no longer available.", self.chat_box)
            return

        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Save generated image",
            source_path.name,
            "PNG image (*.png);;All files (*.*)",
        )
        if not destination:
            return

        destination_path = Path(destination)
        if not destination_path.suffix:
            destination_path = destination_path.with_suffix(source_path.suffix)

        try:
            shutil.copy2(source_path, destination_path)
        except OSError as error:
            QToolTip.showText(QCursor.pos(), f"Could not save image: {error}", self.chat_box)
            return

        QToolTip.showText(QCursor.pos(), "Image saved successfully.", self.chat_box)

    # =============================================================
    # System / Error messages
    # =============================================================

    def append_system_message(self, message: str) -> int:
        message_id = self._register_message("system", message)
        safe = html_lib.escape(message)
        self._insert_block(
            f'<p align="center" style="color:{SYSTEM_TEXT_COLOR}; margin:10px 0;"><i>{safe}</i></p>'
        )
        self.scroll_to_bottom()
        return message_id

    def append_error(self, message: str) -> int:
        message_id = self._register_message("error", message)
        safe = html_lib.escape(message)
        self._insert_block(
            f'<p style="color:{ERROR_TEXT_COLOR}; margin:10px 0;"><b>⚠️ Error:</b> {safe}</p>'
        )
        self.scroll_to_bottom()
        return message_id

    # =============================================================
    # Clear Chat & Welcome Screen
    # =============================================================

    def show_empty_state(self) -> None:
        """Render an ultra-premium, eye-comfortable Bento welcome screen with modern workflow cards."""
        self.clear_chat(reset_state=True)
        from app.utils.paths import get_resource_path
        from app.ui.styles import get_theme_palette
        theme_name = getattr(self, "theme", "light")
        p = get_theme_palette(theme_name)
        is_dark = theme_name in ("dark", "oled", "neon")
        
        logo_path = get_resource_path("assets", "logo.png")
        if not logo_path.exists():
            logo_path = get_resource_path("assets", "logo.ico")
        logo_img_tag = (
            f'<img src="{logo_path.resolve().as_uri()}" width="68" height="68" style="margin-bottom: 12px; border-radius: 14px;"/><br>'
            if logo_path.exists()
            else '<div style="font-size: 38px; margin-bottom: 8px;">✨</div>'
        )

        card_bg = "#1E293B" if is_dark else "#FFFFFF"
        card_border = "#334155" if is_dark else "#E2E8F0"
        badge_bg = "#1E1B4B" if is_dark else "#EEF2FF"
        badge_text = "#C7D2FE" if is_dark else "#4338CA"
        badge_border = "#3730A3" if is_dark else "#C7D2FE"

        # Dedicated pastel icon pill containers for eye-comfort
        doc_icon_bg = "#1E1B4B" if is_dark else "#EEF2FF"
        code_icon_bg = "#064E3B" if is_dark else "#ECFDF5"
        art_icon_bg = "#3B0764" if is_dark else "#FAF5FF"
        voice_icon_bg = "#451A03" if is_dark else "#FFFBEB"

        subtext_color = "#94A3B8" if is_dark else "#64748B"

        welcome_html = f"""
        <div style="text-align: center; margin-top: 32px; margin-bottom: 24px; font-family: 'Segoe UI Variable', 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', 'Noto Sans Bengali', sans-serif;">
            {logo_img_tag}
            <div style="margin-bottom: 12px;">
                <span style="background-color: {badge_bg}; color: {badge_text}; border: 1px solid {badge_border}; border-radius: 14px; padding: 5px 14px; font-size: 9pt; font-weight: 700; letter-spacing: 0.5px;">
                    ✨ JAKARIYA AI STUDIO • NEXT-GEN MULTI-MODEL AI
                </span>
            </div>
            <h1 style="font-size: 24px; font-weight: 800; color: {p['text_chat']}; margin-top: 4px; margin-bottom: 8px; letter-spacing: -0.3px;">
                What would you like to create today?
            </h1>
            <p style="font-size: 10.5pt; color: {subtext_color}; margin-top: 0px; margin-bottom: 26px; line-height: 1.5;">
                Select a quick workflow below or ask any question to get started with autonomous AI intelligence
            </p>

            <table width="100%" cellspacing="12" cellpadding="0" style="max-width: 700px; margin: 0 auto;">
                <tr>
                    <td width="50%">
                        <a href="promptcard:Create%20a%20comprehensive%20business%20proposal%20document%20with%20executive%20summary%2C%20KPI%20data%20tables%2C%20and%20action%20roadmap" style="text-decoration: none;">
                            <table width="100%" cellspacing="0" cellpadding="14" style="background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 14px;">
                                <tr>
                                    <td width="42" valign="middle" align="center" style="background-color: {doc_icon_bg}; border-radius: 10px; font-size: 19pt; padding: 6px;">📄</td>
                                    <td style="padding-left: 12px;">
                                        <b style="color: {p['text_chat']}; font-size: 10.5pt; font-weight: 700;">Smart Documents & Files</b><br>
                                        <span style="color: {subtext_color}; font-size: 9pt; line-height: 1.45;">Generate Word, Excel, PDF or clone templates</span>
                                    </td>
                                </tr>
                            </table>
                        </a>
                    </td>
                    <td width="50%">
                        <a href="promptcard:Write%20a%20production-ready%20Python%20script%20with%20unit%20tests%20and%20error%20handling" style="text-decoration: none;">
                            <table width="100%" cellspacing="0" cellpadding="14" style="background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 14px;">
                                <tr>
                                    <td width="42" valign="middle" align="center" style="background-color: {code_icon_bg}; border-radius: 10px; font-size: 19pt; padding: 6px;">⚡</td>
                                    <td style="padding-left: 12px;">
                                        <b style="color: {p['text_chat']}; font-size: 10.5pt; font-weight: 700;">Code Engine & Analysis</b><br>
                                        <span style="color: {subtext_color}; font-size: 9pt; line-height: 1.45;">Python execution, debugging & data analytics</span>
                                    </td>
                                </tr>
                            </table>
                        </a>
                    </td>
                </tr>
                <tr>
                    <td width="50%">
                        <a href="promptcard:Generate%20an%20image%20of%20a%20futuristic%20minimalist%20floating%20workspace%20with%20soft%20ambient%20glow%20and%20hyper-detailed%20reflections" style="text-decoration: none;">
                            <table width="100%" cellspacing="0" cellpadding="14" style="background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 14px;">
                                <tr>
                                    <td width="42" valign="middle" align="center" style="background-color: {art_icon_bg}; border-radius: 10px; font-size: 19pt; padding: 6px;">🎨</td>
                                    <td style="padding-left: 12px;">
                                        <b style="color: {p['text_chat']}; font-size: 10.5pt; font-weight: 700;">AI Visual Art & Creation</b><br>
                                        <span style="color: {subtext_color}; font-size: 9pt; line-height: 1.45;">High-resolution concepts & photorealistic art</span>
                                    </td>
                                </tr>
                            </table>
                        </a>
                    </td>
                    <td width="50%">
                        <a href="promptcard:Explain%20the%20core%20architecture%20of%20Transformer%20models%20and%20attention%20mechanisms%20in%20clear%20terms" style="text-decoration: none;">
                            <table width="100%" cellspacing="0" cellpadding="14" style="background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 14px;">
                                <tr>
                                    <td width="42" valign="middle" align="center" style="background-color: {voice_icon_bg}; border-radius: 10px; font-size: 19pt; padding: 6px;">🎙️</td>
                                    <td style="padding-left: 12px;">
                                        <b style="color: {p['text_chat']}; font-size: 10.5pt; font-weight: 700;">Deep Research & Voice</b><br>
                                        <span style="color: {subtext_color}; font-size: 9pt; line-height: 1.45;">Continuous voice dialogue & multi-step reasoning</span>
                                    </td>
                                </tr>
                            </table>
                        </a>
                    </td>
                </tr>
            </table>
        </div>
        """
        self._insert_block(welcome_html)

    def clear_chat(self, reset_state: bool = True) -> None:
        self.chat_box.clear()
        if reset_state:
            self._messages.clear()
            self._code_blocks.clear()
            self._next_message_id = 0
            self._next_code_id = 0
            self._stream_raw_text = ""
            self._stream_start_position = None
            self._stream_block_start_position = None
            self._stream_message_id = None

    def get_history(self) -> list[dict]:
        ordered = sorted(self._messages.values(), key=lambda m: m.id)
        return [m.to_dict() for m in ordered]

    def get_api_messages(self) -> list[dict]:
        ordered = sorted(self._messages.values(), key=lambda m: m.id)
        return [
            {"role": m.role, "content": m.content}
            for m in ordered
            if m.role in ("user", "assistant")
        ]

    def load_history(self, history: list[dict]) -> None:
        self.clear_chat(reset_state=True)
        if not history:
            self.show_empty_state()
            return

        for entry in history:
            role = entry.get("role")
            content = entry.get("content", "")
            if role == "user":
                self.append_user_message(content)
            elif role == "assistant":
                self.append_assistant_message(content)
            elif role == "system":
                self.append_system_message(content)
            elif role == "error":
                self.append_error(content)

    def load_messages(
        self,
        messages: Sequence[Message],
        attachments_by_message: dict[str, Sequence[object]] | None = None,
    ) -> None:
        """Render persisted domain messages for the currently selected chat."""
        self.clear_chat(reset_state=True)
        if not messages:
            self.show_empty_state()
            return
        attachments_by_message = attachments_by_message or {}
        for message in messages:
            if message.role == "user":
                self.append_user_message(
                    message.content, attachments_by_message.get(message.id, ())
                )
            elif message.role == "assistant":
                self.append_assistant_message(message.content)
            elif message.role == "system":
                self.append_system_message(message.content)

    # =============================================================
    # Auto Scroll
    # =============================================================

    def scroll_to_bottom(self) -> None:
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        
        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_box.setTextCursor(cursor)
        
        scrollbar = self.chat_box.verticalScrollBar()
        if not hasattr(self, "_scroll_anim"):
            self._scroll_anim = QPropertyAnimation(scrollbar, b"value")
            self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            
        self._scroll_anim.stop()
        self._scroll_anim.setDuration(300)
        self._scroll_anim.setStartValue(scrollbar.value())
        self._scroll_anim.setEndValue(scrollbar.maximum())
        self._scroll_anim.start()

