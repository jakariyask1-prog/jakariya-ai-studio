"""Modern Antigravity-Style Interactive Code Changes & Diff Review Dialog for Jakariya AI Studio."""

from __future__ import annotations

import html as html_lib
import os
import subprocess
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from app.agent.diff_tracker import DiffRecord
from app.utils.paths import get_resource_path


class CodeChangesReviewDialog(QDialog):
    """Interactive Modal Dialog to inspect changed files, directory locations, and unified line diffs."""

    def __init__(
        self,
        changes: List[DiffRecord],
        parent: Optional[QWidget] = None,
        theme: str = "light",
        initial_file: str = "",
    ) -> None:
        super().__init__(parent)
        self.changes = list(changes)
        self.theme = str(theme).lower()
        self.is_dark = self.theme in ("dark", "oled", "neon")
        self.initial_file = initial_file

        self._active_record: Optional[DiffRecord] = None

        self.setWindowTitle("Review Code Changes & Diffs — Jakariya AI Studio")
        self.resize(1080, 720)
        self.setMinimumSize(780, 500)

        # Apply Window Icon
        icon_path = get_resource_path("assets", "logo.ico")
        if not icon_path.exists():
            icon_path = get_resource_path("assets", "logo.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._setup_palette()
        self._setup_ui()
        self._populate_files()

    def _setup_palette(self) -> None:
        """Configure theme colors."""
        if self.is_dark:
            self.col_dialog_bg = "#0F172A"
            self.col_card_bg = "#1E293B"
            self.col_card_border = "#334155"
            self.col_text_main = "#F8FAFC"
            self.col_text_muted = "#94A3B8"
            self.col_input_bg = "#0B1120"
            self.col_input_border = "#334155"
            self.col_item_hover = "#253349"
            self.col_item_selected = "#312E81"
            self.col_diff_bg = "#0B1120"
            self.col_diff_border = "#1E293B"
            self.col_btn_sec_bg = "#1E293B"
            self.col_btn_sec_hover = "#334155"
        else:
            self.col_dialog_bg = "#F8FAFC"
            self.col_card_bg = "#FFFFFF"
            self.col_card_border = "#E2E8F0"
            self.col_text_main = "#0F172A"
            self.col_text_muted = "#64748B"
            self.col_input_bg = "#FFFFFF"
            self.col_input_border = "#CBD5E1"
            self.col_item_hover = "#F1F5F9"
            self.col_item_selected = "#EEF2FF"
            self.col_diff_bg = "#FFFFFF"
            self.col_diff_border = "#E2E8F0"
            self.col_btn_sec_bg = "#F1F5F9"
            self.col_btn_sec_hover = "#E2E8F0"

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.col_dialog_bg};
                color: {self.col_text_main};
                font-family: 'Segoe UI Variable', 'Segoe UI', 'Noto Sans Bengali', sans-serif;
            }}
            QSplitter::handle {{
                background-color: {self.col_card_border};
                width: 2px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Top Header Frame ──────────────────────────────────────────
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.col_card_bg};
                border: 1px solid {self.col_card_border};
                border-radius: 12px;
                padding: 10px 16px;
            }}
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(4, 4, 4, 4)

        # Title & Metric Stats
        title_box = QVBoxLayout()
        title_label = QLabel("📝 Review Code Changes & Diffs (Antigravity Tracker)")
        title_label.setStyleSheet(f"font-size: 13pt; font-weight: 700; color: {self.col_text_main};")

        total_files = len(self.changes)
        total_added = sum(c.lines_added for c in self.changes)
        total_removed = sum(c.lines_removed for c in self.changes)

        badge_bg = "#312E81" if self.is_dark else "#EEF2FF"
        badge_txt = "#C7D2FE" if self.is_dark else "#4F46E5"
        badge_border = "#4338CA" if self.is_dark else "#C7D2FE"

        meta_label = QLabel(
            f'<span style="background-color:{badge_bg}; color:{badge_txt}; border:1px solid {badge_border}; border-radius:6px; padding:2px 8px; font-weight:700; font-size:9.5pt;">{total_files} file{"s" if total_files != 1 else ""} changed</span> '
            f'<span style="color:#16A34A; font-weight:700; font-size:9.5pt; margin-left:8px;">+{total_added} additions</span> '
            f'<span style="color:#DC2626; font-weight:700; font-size:9.5pt; margin-left:8px;">-{total_removed} deletions</span>'
        )
        meta_label.setTextFormat(Qt.TextFormat.RichText)

        title_box.addWidget(title_label)
        title_box.addWidget(meta_label)
        h_layout.addLayout(title_box, 1)

        # Copy All Diffs Button
        self.btn_copy_all = QPushButton("📋 Copy All Diffs")
        self.btn_copy_all.setFixedHeight(34)
        self.btn_copy_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_all.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.col_btn_sec_bg};
                color: {self.col_text_main};
                border: 1px solid {self.col_card_border};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 9.5pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self.col_btn_sec_hover};
            }}
        """)
        self.btn_copy_all.clicked.connect(self._copy_all_diffs)
        h_layout.addWidget(self.btn_copy_all)

        # Close Button
        btn_close = QPushButton("✖ Close")
        btn_close.setFixedHeight(34)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: #4F46E5;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
                font-size: 9.5pt;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #4338CA;
            }}
        """)
        btn_close.clicked.connect(self.accept)
        h_layout.addWidget(btn_close)

        layout.addWidget(header_frame)

        # ── Main Content Splitter ─────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left Pane (Files Sidebar) ────────────────────────────────
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)

        # Search / Filter Box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter files...")
        self.search_input.setFixedHeight(36)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.col_input_bg};
                color: {self.col_text_main};
                border: 1.5px solid {self.col_input_border};
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 9.5pt;
            }}
            QLineEdit:focus {{
                border-color: #6366F1;
            }}
        """)
        self.search_input.textChanged.connect(self._filter_files)
        left_layout.addWidget(self.search_input)

        # File List Widget
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {self.col_card_bg};
                border: 1px solid {self.col_card_border};
                border-radius: 10px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                border-radius: 8px;
                padding: 6px;
                margin-bottom: 3px;
            }}
            QListWidget::item:hover {{
                background-color: {self.col_item_hover};
            }}
            QListWidget::item:selected {{
                background-color: {self.col_item_selected};
                color: {self.col_text_main};
            }}
        """)
        self.file_list.currentRowChanged.connect(self._on_file_selected)
        left_layout.addWidget(self.file_list, 1)

        # Bottom Actions Bar for Left Pane
        left_actions = QHBoxLayout()
        left_actions.setSpacing(6)

        self.btn_open_file = QPushButton("📂 Open File")
        self.btn_open_file.setFixedHeight(32)
        self.btn_open_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_file.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.col_btn_sec_bg};
                color: {self.col_text_main};
                border: 1px solid {self.col_card_border};
                border-radius: 6px;
                font-size: 9pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self.col_btn_sec_hover};
            }}
        """)
        self.btn_open_file.clicked.connect(self._open_current_file)
        left_actions.addWidget(self.btn_open_file)

        self.btn_open_folder = QPushButton("🗂️ Reveal in Explorer")
        self.btn_open_folder.setFixedHeight(32)
        self.btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_folder.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.col_btn_sec_bg};
                color: {self.col_text_main};
                border: 1px solid {self.col_card_border};
                border-radius: 6px;
                font-size: 9pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self.col_btn_sec_hover};
            }}
        """)
        self.btn_open_folder.clicked.connect(self._reveal_in_explorer)
        left_actions.addWidget(self.btn_open_folder)

        left_layout.addLayout(left_actions)
        splitter.addWidget(left_widget)

        # ── Right Pane (Diff Viewer) ─────────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        # Diff Header Bar
        diff_header = QFrame()
        diff_header.setStyleSheet(f"""
            QFrame {{
                background-color: {self.col_card_bg};
                border: 1px solid {self.col_card_border};
                border-radius: 8px;
                padding: 6px 12px;
            }}
        """)
        dh_layout = QHBoxLayout(diff_header)
        dh_layout.setContentsMargins(0, 0, 0, 0)

        self.diff_path_label = QLabel("Select a file to inspect diff")
        self.diff_path_label.setStyleSheet(f"font-size: 10pt; font-weight: 600; color: {self.col_text_main};")
        dh_layout.addWidget(self.diff_path_label, 1)

        self.diff_badge_label = QLabel("")
        self.diff_badge_label.setTextFormat(Qt.TextFormat.RichText)
        dh_layout.addWidget(self.diff_badge_label)

        self.btn_copy_diff = QPushButton("📋 Copy Diff")
        self.btn_copy_diff.setFixedHeight(28)
        self.btn_copy_diff.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_diff.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.col_btn_sec_bg};
                color: {self.col_text_main};
                border: 1px solid {self.col_card_border};
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 8.5pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self.col_btn_sec_hover};
            }}
        """)
        self.btn_copy_diff.clicked.connect(self._copy_current_diff)
        dh_layout.addWidget(self.btn_copy_diff)

        right_layout.addWidget(diff_header)

        # Diff Text Browser
        self.diff_browser = QTextBrowser()
        self.diff_browser.setReadOnly(True)
        self.diff_browser.setFont(QFont("Consolas", 10))
        self.diff_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {self.col_diff_bg};
                border: 1px solid {self.col_diff_border};
                border-radius: 10px;
                padding: 10px;
                font-family: 'Consolas', 'Fira Code', 'Courier New', monospace;
            }}
        """)
        right_layout.addWidget(self.diff_browser, 1)

        splitter.addWidget(right_widget)

        # Set Splitter ratio: 320px left, remainder right
        splitter.setSizes([340, 740])
        layout.addWidget(splitter, 1)

    def _populate_files(self) -> None:
        """Populate the left sidebar with changed files."""
        self.file_list.clear()

        if not self.changes:
            self.diff_path_label.setText("No code changes recorded yet.")
            self.diff_browser.setHtml(
                f'<div style="text-align:center; padding: 40px; color:{self.col_text_muted};">'
                '<h3>No changes recorded</h3>'
                '<p>When the AI Agent creates, modifies, or rewrites files, '
                'unified diffs and change metrics will be tracked and displayed here.</p>'
                '</div>'
            )
            self.btn_copy_all.setEnabled(False)
            self.btn_copy_diff.setEnabled(False)
            self.btn_open_file.setEnabled(False)
            self.btn_open_folder.setEnabled(False)
            return

        initial_row = 0
        for idx, rec in enumerate(self.changes):
            item = QListWidgetItem()
            # Action styling
            act = rec.action.lower()
            if act == "created":
                act_color = "#16A34A" if not self.is_dark else "#4ADE80"
                act_bg = "#DCFCE7" if not self.is_dark else "#14532D"
                act_label = "Created"
            elif act == "overwritten":
                act_color = "#9333EA" if not self.is_dark else "#C084FC"
                act_bg = "#F3E8FF" if not self.is_dark else "#581C87"
                act_label = "Rewritten"
            else:
                act_color = "#D97706" if not self.is_dark else "#FBBF24"
                act_bg = "#FEF3C7" if not self.is_dark else "#78350F"
                act_label = "Modified"

            diff_stat = f"+{rec.lines_added} / -{rec.lines_removed}" if (rec.lines_added or rec.lines_removed) else "0"

            # Custom card widget for item
            card_widget = QWidget()
            card_layout = QVBoxLayout(card_widget)
            card_layout.setContentsMargins(4, 4, 4, 4)
            card_layout.setSpacing(2)

            top_row = QHBoxLayout()
            name_label = QLabel(f"📄 {rec.file_name}")
            name_label.setStyleSheet(f"font-weight: 700; font-size: 10pt; color: {self.col_text_main};")
            top_row.addWidget(name_label, 1)

            # Badge for action
            badge = QLabel(f" {act_label} ")
            badge.setStyleSheet(f"background-color: {act_bg}; color: {act_color}; border-radius: 4px; font-weight: 700; font-size: 8pt; padding: 1px 4px;")
            top_row.addWidget(badge)

            card_layout.addLayout(top_row)

            # Subtitle row: folder & stats
            sub_row = QHBoxLayout()
            folder_label = QLabel(f"📁 {rec.folder}")
            folder_label.setStyleSheet(f"font-size: 8.5pt; color: {self.col_text_muted};")
            sub_row.addWidget(folder_label, 1)

            stat_label = QLabel(
                f'<span style="color:#16A34A; font-weight:600;">+{rec.lines_added}</span> '
                f'<span style="color:#DC2626; font-weight:600;">-{rec.lines_removed}</span>'
            )
            stat_label.setTextFormat(Qt.TextFormat.RichText)
            stat_label.setStyleSheet("font-size: 8.5pt;")
            sub_row.addWidget(stat_label)

            card_layout.addLayout(sub_row)

            item.setSizeHint(card_widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, rec)
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, card_widget)

            if self.initial_file and (self.initial_file in rec.file_path or self.initial_file in rec.file_name):
                initial_row = idx

        self.file_list.setCurrentRow(initial_row)

    def _filter_files(self, text: str) -> None:
        """Filter file list by query string."""
        query = text.strip().lower()
        for idx in range(self.file_list.count()):
            item = self.file_list.item(idx)
            rec: DiffRecord = item.data(Qt.ItemDataRole.UserRole)
            if not rec:
                continue
            visible = not query or (query in rec.file_name.lower() or query in rec.folder.lower() or query in rec.file_path.lower())
            item.setHidden(not visible)

    def _on_file_selected(self, row: int) -> None:
        """Render unified diff when file is selected."""
        if row < 0 or row >= self.file_list.count():
            return
        item = self.file_list.item(row)
        rec: DiffRecord = item.data(Qt.ItemDataRole.UserRole)
        if not rec:
            return

        self._active_record = rec
        self.diff_path_label.setText(f"📄 {rec.file_path}")

        # Header badges
        act = rec.action.capitalize()
        badge_html = (
            f'<span style="font-size:9pt; font-weight:700; margin-right:8px;">{act}</span> '
            f'<span style="color:#16A34A; font-weight:700; font-size:9pt;">+{rec.lines_added}</span> '
            f'<span style="color:#DC2626; font-weight:700; font-size:9pt;">-{rec.lines_removed}</span>'
        )
        self.diff_badge_label.setText(badge_html)

        # Render colored diff
        diff_html = self._format_diff_to_html(rec)
        self.diff_browser.setHtml(diff_html)

    def _format_diff_to_html(self, rec: DiffRecord) -> str:
        """Convert unified diff text into styled HTML."""
        diff_raw = rec.diff_text.strip()
        if not diff_raw:
            # Fallback if file was created or diff was not provided
            if Path(rec.file_path).exists():
                try:
                    content = Path(rec.file_path).read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()[:150]
                    content_preview = "\n".join(f"+ {line}" for line in lines)
                    diff_raw = f"--- /dev/null\n+++ b/{rec.file_name}\n@@ -0,0 +1,{len(lines)} @@\n{content_preview}"
                except Exception:
                    diff_raw = f"# {rec.file_name} ({rec.action})\n# No line-by-line diff available."
            else:
                diff_raw = f"# {rec.file_name} ({rec.action})\n# File does not exist on disk."

        lines_html = []
        bg_added = "rgba(34, 197, 94, 0.12)" if self.is_dark else "#E6F4EA"
        col_added = "#4ADE80" if self.is_dark else "#137333"

        bg_removed = "rgba(239, 68, 68, 0.12)" if self.is_dark else "#FCE8E6"
        col_removed = "#F87171" if self.is_dark else "#C5221F"

        bg_hunk = "rgba(99, 102, 241, 0.15)" if self.is_dark else "#EEF2FF"
        col_hunk = "#A5B4FC" if self.is_dark else "#4F46E5"

        for line in diff_raw.splitlines():
            escaped = html_lib.escape(line)
            if not escaped:
                lines_html.append('<div>&nbsp;</div>')
                continue

            if line.startswith("+++") or line.startswith("---"):
                lines_html.append(
                    f'<div style="font-weight:bold; color:{self.col_text_muted};">{escaped}</div>'
                )
            elif line.startswith("@@"):
                lines_html.append(
                    f'<div style="background-color:{bg_hunk}; color:{col_hunk}; font-weight:700; border-radius:4px; padding:2px 6px; margin:4px 0;">{escaped}</div>'
                )
            elif line.startswith("+"):
                lines_html.append(
                    f'<div style="background-color:{bg_added}; color:{col_added}; border-left:3px solid {col_added}; padding-left:6px; font-weight:500;">{escaped}</div>'
                )
            elif line.startswith("-"):
                lines_html.append(
                    f'<div style="background-color:{bg_removed}; color:{col_removed}; border-left:3px solid {col_removed}; padding-left:6px; font-weight:500;">{escaped}</div>'
                )
            else:
                lines_html.append(
                    f'<div style="color:{self.col_text_muted}; padding-left:9px;">{escaped}</div>'
                )

        body_html = "".join(lines_html)
        return f"""
        <html>
        <body style="font-family:'Consolas', 'Fira Code', 'JetBrains Mono', Courier New, monospace; font-size:10pt; line-height:1.45; white-space:pre-wrap; margin:0;">
            {body_html}
        </body>
        </html>
        """

    def _copy_current_diff(self) -> None:
        """Copy active file's diff to clipboard."""
        if not self._active_record or not self._active_record.diff_text:
            QToolTip.showText(self.btn_copy_diff.mapToGlobal(self.btn_copy_diff.rect().center()), "No diff text to copy!", self)
            return

        QApplication.clipboard().setText(self._active_record.diff_text)
        QToolTip.showText(self.btn_copy_diff.mapToGlobal(self.btn_copy_diff.rect().center()), "✅ Diff Copied!", self)

    def _copy_all_diffs(self) -> None:
        """Copy all diffs across all files to clipboard."""
        if not self.changes:
            return

        parts = []
        for rec in self.changes:
            parts.append(f"diff --git a/{rec.file_name} b/{rec.file_name}")
            parts.append(f"# Action: {rec.action} ({rec.folder}) | +{rec.lines_added} / -{rec.lines_removed}")
            if rec.diff_text.strip():
                parts.append(rec.diff_text.strip())
            else:
                parts.append(f"# File: {rec.file_path}")
            parts.append("\n" + "=" * 60 + "\n")

        full_diff = "\n".join(parts)
        QApplication.clipboard().setText(full_diff)
        QToolTip.showText(self.btn_copy_all.mapToGlobal(self.btn_copy_all.rect().center()), "✅ All Diffs Copied!", self)

    def _open_current_file(self) -> None:
        """Open the currently selected file with the system's default application."""
        if not self._active_record:
            return
        file_path = Path(self._active_record.file_path)
        if not file_path.exists():
            QMessageBox.warning(self, "File Not Found", f"File does not exist on disk:\n{file_path}")
            return
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path.resolve())))

    def _reveal_in_explorer(self) -> None:
        """Reveal file or folder in Windows Explorer."""
        if not self._active_record:
            return
        target = Path(self._active_record.file_path).resolve()
        if target.exists():
            subprocess.run(["explorer", f"/select,{str(target)}"], check=False)
        elif target.parent.exists():
            subprocess.run(["explorer", str(target.parent)], check=False)
        else:
            QMessageBox.warning(self, "Folder Not Found", f"Cannot locate parent directory:\n{target.parent}")
