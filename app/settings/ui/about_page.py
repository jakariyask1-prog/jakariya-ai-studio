"""About page widget for Jakariya AI Studio Settings Window."""

from __future__ import annotations

import sys
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.settings.settings_schema import AboutSettingsSchema


class AboutPage(QWidget):
    """About settings UI page (App Info, Version, Creator, System Details)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # App Header Banner
        self.title_label = QLabel("Jakariya AI Studio")
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #4F46E5;")
        layout.addWidget(self.title_label)

        subtitle_label = QLabel("Desktop Multi-Model AI Workspace & Intelligent Assistant")
        subtitle_label.setStyleSheet("color: #888888; font-size: 13px;")
        layout.addWidget(subtitle_label)

        # Application Details Group Box
        app_group = QGroupBox("Application Metadata")
        app_form = QFormLayout(app_group)
        app_form.setContentsMargins(15, 20, 15, 20)
        app_form.setSpacing(12)

        self.version_label = QLabel("1.0.0")
        app_form.addRow("Application Version:", self.version_label)

        self.creator_label = QLabel("Md. Jakariya Sheikh")
        self.creator_label.setStyleSheet("font-weight: bold;")
        app_form.addRow("Creator & Owner:", self.creator_label)

        app_form.addRow("Architecture:", QLabel("Phase 8 Modular Configuration Engine"))
        app_form.addRow("UI Framework:", QLabel("PySide6 (Qt for Python)"))
        app_form.addRow("Python Runtime:", QLabel(f"Python {sys.version.split()[0]}"))

        layout.addWidget(app_group)

        # System & Environment Info
        sys_group = QGroupBox("System Information")
        sys_form = QFormLayout(sys_group)
        sys_form.setContentsMargins(15, 20, 15, 20)
        sys_form.setSpacing(12)

        sys_form.addRow("Operating System:", QLabel(sys.platform.capitalize()))
        sys_form.addRow("Encoding:", QLabel("UTF-8 (Unicode / Bangla Enabled)"))
        sys_form.addRow("AI Engine:", QLabel("Multi-Model Intelligence (Google, OpenRouter, OpenAI, Anthropic)"))

        layout.addWidget(sys_group)
        layout.addStretch()

    def load_settings(self, settings: AboutSettingsSchema) -> None:
        """Populate UI labels from AboutSettingsSchema object."""
        self.title_label.setText(settings.app_name)
        self.version_label.setText(settings.version)
        self.creator_label.setText(settings.creator)

    def get_settings(self) -> AboutSettingsSchema:
        """Return the About settings state."""
        return AboutSettingsSchema(
            app_name=self.title_label.text(),
            version=self.version_label.text(),
            creator=self.creator_label.text(),
        )
