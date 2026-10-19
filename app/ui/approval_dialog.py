"""PySide6 Tool Permission Approval Dialog."""

from typing import Any, Dict
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QCheckBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QWidget,
)


from app.ui.styles import get_dialog_style, get_theme_palette


class ToolApprovalDialog(QDialog):
    """Professional approval dialog shown when a tool requires explicit user confirmation."""

    def __init__(self, tool_name: str, tool_description: str, params: Dict[str, Any], parent: QWidget = None, theme: str = "light"):
        super().__init__(parent)
        self._theme = str(theme).lower()
        p = get_theme_palette(self._theme)

        self.setWindowTitle("Security Permission Required")
        self.setFixedWidth(520)
        self.setModal(True)
        self.setStyleSheet(get_dialog_style(self._theme))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # Header Title
        title_label = QLabel("🛡️ Permission Approval Required")
        title_label.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {p['input_text']};")

        # Subtitle explanation
        desc_label = QLabel(
            f"The AI Agent is requesting permission to execute the action below using <b>{tool_name}</b>:"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: {p['placeholder_text']}; font-size: 13px; line-height: 1.4;")


        # Details box
        details_box = QTextEdit()
        details_box.setReadOnly(True)
        details_box.setFixedHeight(130)
        details_box.setStyleSheet(
            "QTextEdit { background-color: #0F172A; color: #38BDF8; font-family: 'Fira Code', 'Consolas', monospace; "
            "border: 1px solid #334155; border-radius: 8px; padding: 10px; font-size: 11px; line-height: 1.5; }"
        )

        details_text = f"Tool Name: {tool_name}\nDescription: {tool_description}\nParameters:\n"
        for key, val in params.items():
            details_text += f"  - {key}: {val}\n"

        details_box.setText(details_text)

        # Checkbox for task-wide auto approval
        self.remember_for_task = QCheckBox("⚡ Auto-approve all subsequent actions for this task (No more popups)")
        self.remember_for_task.setToolTip("Once enabled, the AI Agent will execute all subsequent actions in this task autonomously without prompting.")
        self.remember_for_task.setStyleSheet(f"color: {p['input_text']}; font-size: 12px; font-weight: 500;")

        self._allow_all = False

        # Action Buttons Layout (Deny, Allow Once, Allow All)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.deny_button = QPushButton("Deny Action")
        self.deny_button.setFixedHeight(38)
        self.deny_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deny_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {p['btn_secondary_bg']};
                color: {p['btn_secondary_text']};
                border: 1px solid {p['btn_secondary_border']};
                font-weight: 600;
                border-radius: 8px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: {p['btn_secondary_hover']};
                color: {p['input_text']};
                border-color: {p['border_capsule_focus']};
            }}
        """)
        self.deny_button.clicked.connect(self._on_deny)

        self.allow_button = QPushButton("Allow Once")
        self.allow_button.setFixedHeight(38)
        self.allow_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.allow_button.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: #FFFFFF;
                font-weight: 600;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        self.allow_button.clicked.connect(self._on_allow_once)

        self.allow_all_button = QPushButton("⚡ Allow All (Auto Run)")
        self.allow_all_button.setFixedHeight(38)
        self.allow_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.allow_all_button.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #FFFFFF;
                font-weight: 700;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.allow_all_button.clicked.connect(self._on_allow_all)

        button_layout.addWidget(self.deny_button)
        button_layout.addWidget(self.allow_button)
        button_layout.addWidget(self.allow_all_button)

        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addWidget(details_box)
        layout.addWidget(self.remember_for_task)
        layout.addLayout(button_layout)

    @property
    def is_allow_all(self) -> bool:
        """Return True if user chose to auto-approve all subsequent actions for this task."""
        return bool(self._allow_all or self.remember_for_task.isChecked())

    def _on_deny(self) -> None:
        self._allow_all = False
        self.reject()

    def _on_allow_once(self) -> None:
        self._allow_all = self.remember_for_task.isChecked()
        self.accept()

    def _on_allow_all(self) -> None:
        self._allow_all = True
        self.accept()
