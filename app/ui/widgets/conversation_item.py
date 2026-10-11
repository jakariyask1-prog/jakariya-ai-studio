"""Reusable sidebar row for a single conversation with modern active indicators."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QToolButton, QCheckBox


class ConversationItem(QFrame):
    """Render one conversation with a left accent indicator and modern hover styling."""

    selected = Signal(str)
    rename_requested = Signal(str)
    delete_requested = Signal(str)
    check_state_changed = Signal(str, bool)

    def __init__(self, conversation_id: str, title: str, parent=None) -> None:
        super().__init__(parent)
        self.conversation_id = conversation_id
        self._is_selected = False
        self._check_mode = False

        self.setObjectName("conversationItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(title)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(8)

        # Checkbox for Multi-Select Bulk Delete Mode
        self.checkbox = QCheckBox()
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1.5px solid #94A3B8;
            }
            QCheckBox::indicator:checked {
                background-color: #4F46E5;
                border-color: #4F46E5;
            }
        """)
        self.checkbox.toggled.connect(self._on_check_toggled)
        self.checkbox.hide()
        layout.addWidget(self.checkbox)

        # Chat Icon
        self.icon_label = QLabel("💬")
        self.icon_label.setStyleSheet("font-size: 11pt; color: #64748B;")
        layout.addWidget(self.icon_label)

        # Title Label
        self._raw_title = title
        self.title_label = QLabel()
        self.title_label.setObjectName("conversationTitle")
        self.title_label.setWordWrap(False)
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        from PySide6.QtWidgets import QSizePolicy
        self.title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.title_label.setMinimumWidth(0)
        layout.addWidget(self.title_label, 1)

        # Options Menu Button (⋮)
        self.menu_button = QToolButton()
        self.menu_button.setObjectName("conversationMenuButton")
        self.menu_button.setText("⋮")
        self.menu_button.setToolTip("Chat options")
        self.menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_button.clicked.connect(self._show_menu)
        layout.addWidget(self.menu_button)

        self._theme = "light"
        self._apply_style()

    def set_check_mode(self, enabled: bool) -> None:
        """Toggle multi-select checkbox mode visibility."""
        self._check_mode = enabled
        if enabled:
            self.checkbox.show()
            self.menu_button.hide()
        else:
            self.checkbox.hide()
            self.checkbox.setChecked(False)
            self.menu_button.show()

    def set_checked(self, checked: bool) -> None:
        """Set checkbox state programmatically."""
        self.checkbox.setChecked(checked)

    def is_checked(self) -> bool:
        """Return True if item checkbox is selected."""
        return self.checkbox.isChecked()

    def _on_check_toggled(self, checked: bool) -> None:
        self.check_state_changed.emit(self.conversation_id, checked)

    def set_title(self, title: str) -> None:
        """Refresh the visible title after a rename operation."""
        self._raw_title = title
        self.setToolTip(title)
        self._update_elided_title()

    def set_selected(self, selected: bool) -> None:
        """Update visual state when the active conversation changes."""
        if self._is_selected == selected:
            return
        self._is_selected = selected
        self._apply_style()

    def set_theme(self, theme_name: str) -> None:
        """Set active theme and update styles."""
        self._theme = theme_name
        self._apply_style()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_title()

    def _update_elided_title(self) -> None:
        """Elide title text cleanly if it exceeds available label width."""
        available_width = self.title_label.width()
        if available_width <= 10:
            available_width = 160
        from PySide6.QtGui import QFontMetrics
        metrics = QFontMetrics(self.title_label.font())
        elided = metrics.elidedText(self._raw_title, Qt.TextElideMode.ElideRight, available_width)
        self.title_label.setText(elided)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._check_mode:
                self.checkbox.setChecked(not self.checkbox.isChecked())
            else:
                self.selected.emit(self.conversation_id)
        super().mousePressEvent(event)

    def _show_menu(self) -> None:
        menu = QMenu(self)
        rename_action = menu.addAction("✏️ Rename chat")
        delete_action = menu.addAction("🗑️ Delete chat")

        chosen_action = menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))
        if chosen_action == rename_action:
            self.rename_requested.emit(self.conversation_id)
        elif chosen_action == delete_action:
            self.delete_requested.emit(self.conversation_id)

    def _apply_style(self) -> None:
        from app.ui.styles import get_theme_palette
        p = get_theme_palette(self._theme)

        if self._is_selected:
            background = p["item_selected"]
            border_style = "border: none;"
            title_color = p["item_selected_text"]
            title_weight = "600"
            icon_color = p["item_selected_border"]
        else:
            background = "transparent"
            border_style = "border: none;"
            title_color = p["btn_secondary_text"]
            title_weight = "normal"
            icon_color = p["placeholder_text"]

        self.icon_label.setStyleSheet(f"font-size: 11pt; color: {icon_color}; border: none; background: transparent;")

        self.setStyleSheet(
            f"""
            QFrame#conversationItem {{
                background-color: {background};
                border-radius: 10px;
                {border_style}
            }}
            QFrame#conversationItem:hover {{
                background-color: {p['item_hover']};
            }}
            QLabel#conversationTitle {{
                color: {title_color};
                font-size: 10.5pt;
                font-weight: {title_weight};
                background: transparent;
                border: none;
            }}
            QToolButton#conversationMenuButton {{
                color: {p['placeholder_text']};
                border: none;
                background: transparent;
                border-radius: 6px;
                font-size: 14px;
                padding: 2px 6px;
            }}
            QToolButton#conversationMenuButton:hover {{
                background-color: {p['btn_secondary_hover']};
                color: {p['combo_popup_text']};
            }}
            """
        )
        self._update_elided_title()

