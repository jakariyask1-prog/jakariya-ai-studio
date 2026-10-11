"""Dialog used to rename one conversation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
)
from app.ui.styles import INPUT_STYLE, get_dialog_style, get_theme_palette


class RenameChatDialog(QDialog):
    """Collect a replacement title without knowing how chats are stored."""

    def __init__(self, current_title: str, parent=None, theme: str = "light") -> None:
        super().__init__(parent)
        self._theme = str(theme).lower()
        p = get_theme_palette(self._theme)

        self.setWindowTitle("Rename Chat")
        self.setMinimumWidth(380)
        self.setStyleSheet(get_dialog_style(self._theme))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title_label = QLabel("✏️ Rename Chat")
        title_label.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {p['input_text']};")
        layout.addWidget(title_label)

        sub_label = QLabel("Enter a new title for this conversation:")
        sub_label.setStyleSheet(f"font-size: 10pt; color: {p['placeholder_text']};")
        layout.addWidget(sub_label)


        self.title_input = QLineEdit(current_title)
        self.title_input.setMaxLength(60)
        self.title_input.setFixedHeight(38)
        self.title_input.setStyleSheet(INPUT_STYLE)
        self.title_input.selectAll()
        layout.addWidget(self.title_input)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #EF4444; font-size: 10pt;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedHeight(36)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #E2E8F0; color: #0F172A; }
        """)
        self.cancel_button.clicked.connect(self.reject)

        self.save_button = QPushButton("Save Title")
        self.save_button.setFixedHeight(36)
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        self.save_button.clicked.connect(self.accept)

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)

    @property
    def title(self) -> str:
        """Return the trimmed title entered by the user."""
        return self.title_input.text().strip()

    def accept(self) -> None:
        """Keep the dialog open until it contains a valid non-empty title."""
        if not self.title:
            self.error_label.setText("Chat title cannot be empty.")
            self.error_label.show()
            self.title_input.setFocus()
            return
        super().accept()
