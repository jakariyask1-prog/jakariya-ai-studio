"""Dialog for adding custom or cloned voice IDs for TTS engines."""

from __future__ import annotations

from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QLabel,
    QMessageBox,
)
from app.ui.styles import get_dialog_style, get_theme_palette


class AddVoiceDialog(QDialog):
    """Modal dialog allowing users to add a custom/cloned Voice ID to their settings."""

    def __init__(self, parent=None, theme: str = "light", default_provider: str = "cartesia") -> None:
        super().__init__(parent)
        self._theme = str(theme).lower()
        p = get_theme_palette(self._theme)

        self.setWindowTitle("➕ Add Custom Voice ID")
        self.resize(480, 320)
        self.setStyleSheet(get_dialog_style(self._theme))

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("🎙️ Add Custom / Cloned Voice")
        title.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {p['input_text']}; margin-bottom: 4px;")
        layout.addWidget(title)

        desc = QLabel(
            "Add your personal cloned voice or custom speaker ID from Cartesia AI, ElevenLabs, "
            "Edge Neural, or Fish Audio to use directly inside Jakariya AI Studio."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6B7280; font-size: 11px; margin-bottom: 10px;")
        layout.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(12)

        # 1. Voice Name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. My Cloned Voice (Bangla)")
        form.addRow("Voice Name / Label:", self.name_edit)

        # 2. Voice ID
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("e.g. 2c8d7dfb-ca84-4888-9600-8d8c54022dba")
        form.addRow("Voice ID / UUID:", self.id_edit)

        # 3. TTS Engine
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Cartesia AI (Sonic Ultra-Fast)", "cartesia")
        self.provider_combo.addItem("ElevenLabs Multilingual v2", "elevenlabs")
        self.provider_combo.addItem("Edge Neural TTS (Free)", "edge_neural_tts")
        self.provider_combo.addItem("Fish Audio TTS", "fish_audio")

        # Select default provider
        idx = self.provider_combo.findData(default_provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)

        form.addRow("TTS Engine:", self.provider_combo)
        layout.addLayout(form)

        tip_label = QLabel(
            "💡 Tip: For Cartesia personal voice, copy the Voice ID from play.cartesia.ai/voices. "
            "For ElevenLabs, copy the Voice ID from elevenlabs.io/voices."
        )
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("color: #9CA3AF; font-size: 10.5px; font-style: italic;")
        layout.addWidget(tip_label)

        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton("Save Voice")
        self.btn_save.setFixedHeight(36)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-weight: 700;
                padding: 0 18px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        self.btn_save.clicked.connect(self._on_save)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

    def _on_save(self) -> None:
        name = self.name_edit.text().strip()
        voice_id = self.id_edit.text().strip()

        if not voice_id:
            QMessageBox.warning(self, "Missing Voice ID", "Please enter a valid Voice ID.")
            self.id_edit.setFocus()
            return

        if not name:
            self.name_edit.setText(voice_id[:16])

        self.accept()

    def get_voice_data(self) -> dict[str, str]:
        """Return the collected custom voice dict."""
        return {
            "name": self.name_edit.text().strip() or self.id_edit.text().strip()[:16],
            "id": self.id_edit.text().strip(),
            "provider_id": self.provider_combo.currentData(),
        }
