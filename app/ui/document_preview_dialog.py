"""Full-Screen / Modal Document Preview Dialog for Smart Document Cards."""

import html as html_lib
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QFrame,
    QApplication,
    QFileDialog,
    QMessageBox,
)

from app.utils.markdown_renderer import render_markdown
from app.utils.paths import get_resource_path


class DocumentPreviewDialog(QDialog):
    """Full-Screen Modal Preview Dialog displaying rendered AI documents with quick export options."""

    def __init__(
        self,
        title: str,
        document_type: str,
        word_count: int,
        estimated_pages: int,
        raw_content: str,
        parent=None,
        theme: str = "light",
    ):
        super().__init__(parent)
        self.raw_content = raw_content
        self.doc_title = title
        self.doc_type = document_type
        self.theme = str(theme).lower()
        is_dark = self.theme in ("dark", "oled", "neon")

        self.setWindowTitle(f"Document Preview — {title}")
        self.resize(950, 750)
        self.setMinimumSize(700, 500)

        if is_dark:
            self.setStyleSheet("QDialog { background-color: #12121E; color: #F8FAFC; }")

        icon_path = get_resource_path("assets", "logo.ico")
        if not icon_path.exists():
            icon_path = get_resource_path("assets", "logo.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Top Header Frame
        header_bg = "#1E1E2E" if is_dark else "#F8FAFC"
        header_border = "#334155" if is_dark else "#E2E8F0"
        title_color = "#F8FAFC" if is_dark else "#0F172A"
        badge_bg = "#312E81" if is_dark else "#EEF2FF"
        badge_color = "#C7D2FE" if is_dark else "#4F46E5"
        badge_border = "#4338CA" if is_dark else "#C7D2FE"
        meta_color = "#94A3B8" if is_dark else "#64748B"

        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {header_bg};
                border: 1px solid {header_border};
                border-radius: 12px;
                padding: 12px 16px;
            }}
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(4, 4, 4, 4)

        # Title & Badges
        left_layout = QVBoxLayout()
        title_label = QLabel(f"📄 {html_lib.escape(title)}")
        title_label.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {title_color};")

        meta_label = QLabel(
            f'<span style="background-color:{badge_bg}; color:{badge_color}; border:1px solid {badge_border}; border-radius:6px; padding:2px 8px; font-weight:700; font-size:9pt;">{html_lib.escape(document_type)}</span> '
            f'<span style="color:{meta_color}; font-size:9.5pt; margin-left:8px;">~{estimated_pages} page{"s" if estimated_pages > 1 else ""} • {word_count} words</span>'
        )
        meta_label.setTextFormat(Qt.TextFormat.RichText)

        left_layout.addWidget(title_label)
        left_layout.addWidget(meta_label)

        header_layout.addLayout(left_layout, 1)

        # Close button
        close_btn = QPushButton("✖ Close")
        close_btn.setFixedSize(90, 34)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn_bg = "#334155" if is_dark else "#F1F5F9"
        close_btn_fg = "#F8FAFC" if is_dark else "#475569"
        close_btn_border = "#475569" if is_dark else "#CBD5E1"
        close_btn_hover = "#475569" if is_dark else "#E2E8F0"

        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {close_btn_bg};
                color: {close_btn_fg};
                border: 1px solid {close_btn_border};
                border-radius: 8px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {close_btn_hover};
                color: #FFFFFF;
            }}
        """)
        close_btn.clicked.connect(self.accept)
        header_layout.addWidget(close_btn)

        layout.addWidget(header_frame)

        # Central Markdown Document Content View
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        tb_bg = "#1E1E2E" if is_dark else "#FFFFFF"
        tb_fg = "#CDD6F4" if is_dark else "#0F172A"
        tb_border = "#334155" if is_dark else "#E2E8F0"

        self.text_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {tb_bg};
                color: {tb_fg};
                border: 1px solid {tb_border};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        
        rendered_html, _, _ = render_markdown(raw_content)
        self.text_browser.setHtml(rendered_html)
        layout.addWidget(self.text_browser, 1)

        # Bottom Action Bar — Download / Export / Copy
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        # -- Save As (Markdown) --
        btn_save_md = QPushButton("⬇ Save as MD")
        btn_save_md.setFixedHeight(36)
        btn_save_md.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_md.setToolTip("Download the document as a Markdown (.md) file")
        btn_save_md.setStyleSheet(self._action_btn_style("#4F46E5", "#4338CA"))
        btn_save_md.clicked.connect(lambda: self._save_as(".md", "Markdown Files (*.md)"))
        action_layout.addWidget(btn_save_md)

        # -- Save As (TXT) --
        btn_save_txt = QPushButton("📥 Save as TXT")
        btn_save_txt.setFixedHeight(36)
        btn_save_txt.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_txt.setToolTip("Download the document as a plain text (.txt) file")
        btn_save_txt.setStyleSheet(self._action_btn_style("#0F766E", "#0D9488"))
        btn_save_txt.clicked.connect(lambda: self._save_as(".txt", "Text Files (*.txt)"))
        action_layout.addWidget(btn_save_txt)

        # -- Export PDF --
        btn_pdf = QPushButton("📄 Export PDF")
        btn_pdf.setFixedHeight(36)
        btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pdf.setToolTip("Export as PDF")
        btn_pdf.setStyleSheet(self._action_btn_style("#DC2626", "#B91C1C"))
        btn_pdf.clicked.connect(self._export_pdf)
        action_layout.addWidget(btn_pdf)

        # -- Export DOCX --
        btn_docx = QPushButton("📝 Export DOCX")
        btn_docx.setFixedHeight(36)
        btn_docx.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_docx.setToolTip("Export as Word Document (.docx)")
        btn_docx.setStyleSheet(self._action_btn_style("#1D4ED8", "#1E40AF"))
        btn_docx.clicked.connect(self._export_docx)
        action_layout.addWidget(btn_docx)

        action_layout.addStretch(1)

        # -- Copy --
        copy_btn = QPushButton("📋 Copy")
        copy_btn.setFixedHeight(36)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {close_btn_bg};
                color: {close_btn_fg};
                border: 1px solid {close_btn_border};
                border-radius: 8px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: {close_btn_hover};
                color: #FFFFFF;
            }}
        """)
        copy_btn.clicked.connect(self._copy_to_clipboard)
        action_layout.addWidget(copy_btn)

        layout.addLayout(action_layout)

    @staticmethod
    def _action_btn_style(color: str, hover: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                padding: 0 14px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
        """

    def _safe_filename(self, ext: str) -> str:
        """Generate a safe filename from the document title."""
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in self.doc_title).strip() or "document"
        return safe[:80] + ext

    def _save_as(self, ext: str, file_filter: str) -> None:
        """Save the raw markdown content as a text-based file."""
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Save Document As...",
            self._safe_filename(ext),
            f"{file_filter};;All Files (*.*)",
        )
        if not destination:
            return
        dest = Path(destination)
        if not dest.suffix:
            dest = dest.with_suffix(ext)
        try:
            dest.write_text(self.raw_content, encoding="utf-8")
            QApplication.clipboard().setText(str(dest))  # handy: puts path on clipboard
            QMessageBox.information(self, "Saved", f"✅ Document saved to:\n{dest}")
        except OSError as exc:
            QMessageBox.warning(self, "Save Failed", f"❌ Could not save file:\n{exc}")

    def _export_pdf(self) -> None:
        """Export document as PDF using the built-in PDF exporter."""
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Export as PDF",
            self._safe_filename(".pdf"),
            "PDF Files (*.pdf);;All Files (*.*)",
        )
        if not destination:
            return
        dest = Path(destination)
        if not dest.suffix:
            dest = dest.with_suffix(".pdf")
        try:
            from app.export.business_logic.exporter_registry import build_default_exporter_registry
            from app.export.export_options import ExportOptions
            from app.export.models import ExportConversation, ExportMessage
            registry = build_default_exporter_registry()
            exporter = registry.get("pdf")
            conv = ExportConversation(
                title=self.doc_title,
                messages=[ExportMessage(role="assistant", content=self.raw_content)],
            )
            exporter.export(conv, dest, ExportOptions("pdf"))
            QMessageBox.information(self, "Exported", f"✅ PDF saved to:\n{dest}")
        except Exception as exc:
            QMessageBox.warning(self, "PDF Export Failed", f"❌ Could not export PDF:\n{exc}")

    def _export_docx(self) -> None:
        """Export document as DOCX using the built-in DOCX exporter."""
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Export as Word Document",
            self._safe_filename(".docx"),
            "Word Documents (*.docx);;All Files (*.*)",
        )
        if not destination:
            return
        dest = Path(destination)
        if not dest.suffix:
            dest = dest.with_suffix(".docx")
        try:
            from app.export.business_logic.exporter_registry import build_default_exporter_registry
            from app.export.export_options import ExportOptions
            from app.export.models import ExportConversation, ExportMessage
            registry = build_default_exporter_registry()
            exporter = registry.get("docx")
            conv = ExportConversation(
                title=self.doc_title,
                messages=[ExportMessage(role="assistant", content=self.raw_content)],
            )
            exporter.export(conv, dest, ExportOptions("docx"))
            QMessageBox.information(self, "Exported", f"✅ DOCX saved to:\n{dest}")
        except Exception as exc:
            QMessageBox.warning(self, "DOCX Export Failed", f"❌ Could not export DOCX:\n{exc}")

    def _copy_to_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self.raw_content)
        QMessageBox.information(self, "Copied", "✅ Document content copied to clipboard!")
