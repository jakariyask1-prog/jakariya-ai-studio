"""Conversation sidebar UI.

The sidebar renders data passed in by MainWindow and emits user intent.
It never accesses the database or ChatManager directly.
"""

from __future__ import annotations

from typing import Sequence
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QLabel,
)

from app.models.conversation import Conversation
from app.ui.widgets.conversation_item import ConversationItem


class Sidebar(QWidget):
    """Left sidebar widget managing chats, search, import, and bulk delete mode."""

    new_chat_requested = Signal()
    import_requested = Signal()
    conversation_selected = Signal(str)
    rename_requested = Signal(str)
    delete_requested = Signal(str)
    bulk_delete_requested = Signal(list)
    search_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(280)
        self.setMinimumWidth(260)
        self.setMaximumWidth(320)
        self._is_check_mode = False
        self._selected_ids: set[str] = set()
        self._current_theme = "light"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Brand Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 4, 4, 4)
        header_layout.setSpacing(8)

        from PySide6.QtGui import QPixmap
        from app.utils.paths import get_resource_path
        logo_path = get_resource_path("assets", "logo.png")
        if not logo_path.exists():
            logo_path = get_resource_path("assets", "logo.ico")

        if logo_path.exists():
            logo_label = QLabel()
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                scaled_pix = pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                scaled_pix.setDevicePixelRatio(2.0)
                logo_label.setPixmap(scaled_pix)
                logo_label.setFixedSize(32, 32)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            header_layout.addWidget(logo_label)

        self.title_label = QLabel("Jakariya AI Studio")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.title_label.setStyleSheet("font-weight: 700; font-size: 15px; font-family: 'Segoe UI Variable', sans-serif;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        # Action Buttons: Full-width "+ New Chat", "📥" Import, and "☑️" Select Mode Button
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(6)

        self.new_chat_button = QPushButton("＋ New Chat")
        self.new_chat_button.setFixedHeight(38)
        self.new_chat_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_chat_button.clicked.connect(self.new_chat_requested.emit)

        self.import_button = QToolButton()
        self.import_button.setText("📥")
        self.import_button.setFixedSize(38, 38)
        self.import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_button.setToolTip("Import conversation file (JSON, TXT, MD)")
        self.import_button.clicked.connect(self.import_requested.emit)

        self.select_mode_button = QToolButton()
        self.select_mode_button.setText("☑️")
        self.select_mode_button.setFixedSize(38, 38)
        self.select_mode_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_mode_button.setToolTip("Toggle multi-select mode to delete multiple chats at once")
        self.select_mode_button.setCheckable(True)
        self.select_mode_button.clicked.connect(self.toggle_check_mode)

        buttons_layout.addWidget(self.new_chat_button, 1)
        buttons_layout.addWidget(self.import_button)
        buttons_layout.addWidget(self.select_mode_button)

        # Bulk Action Header Bar (Visible during Select Mode)
        self.bulk_bar = QWidget()
        bulk_layout = QHBoxLayout(self.bulk_bar)
        bulk_layout.setContentsMargins(4, 2, 4, 2)
        bulk_layout.setSpacing(6)

        self.select_all_cb = QCheckBox("Select All")
        self.select_all_cb.toggled.connect(self._on_select_all_toggled)

        self.delete_selected_btn = QPushButton("🗑️ Delete (0)")
        self.delete_selected_btn.setFixedHeight(30)
        self.delete_selected_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                font-size: 9pt;
                padding: 2px 8px;
            }
            QPushButton:hover { background-color: #DC2626; }
            QPushButton:disabled { background-color: #FCA5A5; }
        """)
        self.delete_selected_btn.setEnabled(False)
        self.delete_selected_btn.clicked.connect(self._on_bulk_delete_clicked)

        bulk_layout.addWidget(self.select_all_cb)
        bulk_layout.addStretch()
        bulk_layout.addWidget(self.delete_selected_btn)
        self.bulk_bar.hide()

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search chats...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(36)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._emit_search_changed)
        self.search_input.textChanged.connect(self._queue_search)

        # Conversation QListWidget Container
        self.chat_list = QListWidget()
        self.chat_list.setObjectName("conversationList")
        self.chat_list.setFrameShape(QFrame.Shape.NoFrame)
        self.chat_list.setSpacing(3)

        # Empty state label for zero search results
        self.empty_search_label = QLabel("No conversations found")
        self.empty_search_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_search_label.hide()

        layout.addLayout(header_layout)
        layout.addLayout(buttons_layout)
        layout.addWidget(self.bulk_bar)
        layout.addWidget(self.search_input)
        layout.addWidget(self.empty_search_label)
        layout.addWidget(self.chat_list, 1)

        self.apply_theme("light")

    def apply_theme(self, theme_name: str) -> None:
        """Apply active theme styles to sidebar container and child widgets."""
        self._current_theme = theme_name
        from app.ui.styles import get_theme_palette
        p = get_theme_palette(theme_name)

        new_btn_bg = "#202123" if theme_name == "light" else "#10A37F"
        new_btn_hover = "#343541" if theme_name == "light" else "#0D8A6C"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {p['bg_sidebar']};
                color: {p['text_chat']};
            }}
            QFrame {{
                border-right: 1px solid {p['border_sidebar']};
            }}
        """)
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {p['text_chat']}; font-family: 'Segoe UI Variable', sans-serif;")

        self.new_chat_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {new_btn_bg};
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                font-weight: 600;
                font-size: 10.5pt;
            }}
            QPushButton:hover {{ background-color: {new_btn_hover}; }}
        """)

        tool_btn_style = f"""
            QToolButton {{
                background-color: {p['btn_secondary_bg']};
                color: {p['btn_secondary_text']};
                border: 1px solid {p['btn_secondary_border']};
                border-radius: 10px;
                font-size: 11pt;
            }}
            QToolButton:hover {{
                background-color: {p['btn_secondary_hover']};
                border-color: {p['border_capsule_focus']};
            }}
            QToolButton:checked {{
                background-color: {p['item_selected']};
                border-color: {p['item_selected_border']};
                color: {p['item_selected_text']};
            }}
        """
        self.import_button.setStyleSheet(tool_btn_style)
        self.select_mode_button.setStyleSheet(tool_btn_style)

        self.select_all_cb.setStyleSheet(f"font-size: 9.5pt; color: {p['btn_secondary_text']}; font-weight: 600;")
        self.empty_search_label.setStyleSheet(f"color: {p['placeholder_text']}; font-size: 9.5pt; font-style: italic; padding: 12px;")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {p['btn_secondary_bg']};
                color: {p['input_text']};
                border: 1px solid {p['btn_secondary_border']};
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 10pt;
            }}
            QLineEdit:focus {{
                border-color: {p['border_capsule_focus']};
            }}
        """)
        self.chat_list.setStyleSheet("""
            QListWidget#conversationList {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget#conversationList::item {
                border: none;
                padding: 0;
            }
        """)

        for i in range(self.chat_list.count()):
            item = self.chat_list.item(i)
            w = self.chat_list.itemWidget(item)
            if hasattr(w, "set_theme"):
                w.set_theme(theme_name)

        # Sync existing items
        for i in range(self.chat_list.count()):
            item = self.chat_list.item(i)
            widget = self.chat_list.itemWidget(item)
            if isinstance(widget, ConversationItem):
                widget.set_theme(theme_name)

    def toggle_check_mode(self, enabled: bool = None) -> None:
        """Toggle multi-select bulk delete mode ON/OFF."""
        if enabled is None:
            enabled = self.select_mode_button.isChecked()

        self._is_check_mode = enabled
        self.select_mode_button.setChecked(enabled)
        self.bulk_bar.setVisible(enabled)
        self._selected_ids.clear()
        self._update_delete_button()

        # Update all current rows
        for i in range(self.chat_list.count()):
            item = self.chat_list.item(i)
            widget = self.chat_list.itemWidget(item)
            if isinstance(widget, ConversationItem):
                widget.set_check_mode(enabled)

    def set_conversations(
        self,
        conversations: Sequence[Conversation],
        active_conversation_id: str | None,
    ) -> None:
        """Render the sidebar from the conversation state supplied by the UI."""
        self.chat_list.clear()

        if not conversations and self.search_input.text().strip():
            self.empty_search_label.show()
        else:
            self.empty_search_label.hide()

        for conversation in conversations:
            list_item = QListWidgetItem(self.chat_list)
            row = ConversationItem(conversation.id, conversation.title)
            row.set_theme(self._current_theme)
            row.set_selected(conversation.id == active_conversation_id)
            row.set_check_mode(self._is_check_mode)
            row.selected.connect(self.conversation_selected.emit)
            row.rename_requested.connect(self.rename_requested.emit)
            row.delete_requested.connect(self.delete_requested.emit)
            row.check_state_changed.connect(self._on_item_check_changed)

            list_item.setSizeHint(row.sizeHint())
            self.chat_list.setItemWidget(list_item, row)



    def _on_item_check_changed(self, conversation_id: str, checked: bool) -> None:
        if checked:
            self._selected_ids.add(conversation_id)
        else:
            self._selected_ids.discard(conversation_id)
        self._update_delete_button()

    def _on_select_all_toggled(self, checked: bool) -> None:
        """Select or deselect all visible conversation items at once."""
        for i in range(self.chat_list.count()):
            item = self.chat_list.item(i)
            widget = self.chat_list.itemWidget(item)
            if isinstance(widget, ConversationItem):
                widget.set_checked(checked)

    def _update_delete_button(self) -> None:
        count = len(self._selected_ids)
        self.delete_selected_btn.setText(f"🗑️ Delete ({count})")
        self.delete_selected_btn.setEnabled(count > 0)

    def _on_bulk_delete_clicked(self) -> None:
        if self._selected_ids:
            self.bulk_delete_requested.emit(list(self._selected_ids))
            self.toggle_check_mode(False)

    def _queue_search(self, _text: str) -> None:
        """Debounce title search while the user is typing."""
        self._search_timer.start()

    def _emit_search_changed(self) -> None:
        self.search_changed.emit(self.search_input.text().strip())

    def clear_search(self) -> None:
        """Clear the search input and reset full chat history visibility."""
        self.search_input.clear()

