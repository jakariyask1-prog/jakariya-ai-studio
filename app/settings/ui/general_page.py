"""General settings page widget for Jakariya AI Studio Settings Window."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.settings.settings_schema import GeneralSettings


class GeneralPage(QWidget):
    """General settings UI page (Language, User Age, Auto-startup, Notifications)."""

    setting_changed = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 8)
        layout.setSpacing(10)

        # Title & Subtitle
        title_label = QLabel("⚙️ General Preferences")
        title_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title_label)

        desc_label = QLabel("Configure application startup, user profile age, system notifications, and primary UI language.")
        desc_label.setProperty("subtext", "true")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Settings Group Box
        group = QGroupBox("Application Preferences")
        form_layout = QFormLayout(group)
        form_layout.setContentsMargins(14, 12, 14, 12)
        form_layout.setSpacing(10)

        # Language Combo
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("বাংলা (Bengali)", "bn")
        self.lang_combo.currentIndexChanged.connect(self._on_changed)
        form_layout.addRow("Interface Language:", self.lang_combo)

        # User Age SpinBox
        self.age_spin = QSpinBox()
        self.age_spin.setRange(0, 120)
        self.age_spin.setSpecialValueText("Auto-detect from chat / Not set")
        self.age_spin.setSuffix(" years old")
        self.age_spin.setToolTip("If 18 or below, AI will address you as 'তুমি' in Bengali. Above 18 or 0 uses respectful 'আপনি'.")
        self.age_spin.valueChanged.connect(self._on_changed)
        form_layout.addRow("User Age (বয়স):", self.age_spin)

        # Auto Startup Checkbox
        self.startup_check = QCheckBox("Launch Jakariya AI Studio automatically on system startup")
        self.startup_check.toggled.connect(self._on_changed)
        form_layout.addRow("System Startup:", self.startup_check)

        # Notifications Checkbox
        self.notif_check = QCheckBox("Enable desktop notifications for long-running AI tasks")
        self.notif_check.toggled.connect(self._on_changed)
        form_layout.addRow("Notifications:", self.notif_check)

        layout.addWidget(group)
        layout.addStretch()

    def _on_changed(self) -> None:
        self.setting_changed.emit("general", self.get_settings())

    def load_settings(self, settings: GeneralSettings) -> None:
        """Populate UI controls from GeneralSettings object."""
        self.blockSignals(True)
        idx = self.lang_combo.findData(settings.language)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.age_spin.setValue(getattr(settings, "user_age", 0))
        self.startup_check.setChecked(settings.auto_startup)
        self.notif_check.setChecked(settings.notifications_enabled)
        self.blockSignals(False)

    def get_settings(self) -> GeneralSettings:
        """Return GeneralSettings object constructed from active UI values."""
        return GeneralSettings(
            language=self.lang_combo.currentData() or "en",
            auto_startup=self.startup_check.isChecked(),
            notifications_enabled=self.notif_check.isChecked(),
            user_age=self.age_spin.value(),
        )
