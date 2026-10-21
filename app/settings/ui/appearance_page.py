"""Appearance and theme settings page widget for Jakariya AI Studio Settings Window."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.settings.settings_schema import AppearanceSettings


class AppearancePage(QWidget):
    """Appearance settings UI page (Themes, Fonts, Scale, Density)."""

    setting_changed = Signal(str, object)
    theme_preview_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 8)
        layout.setSpacing(10)

        # Title & Subtitle Banner
        title_label = QLabel("🎨 Appearance & Themes")
        title_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title_label)

        desc_label = QLabel("Customize theme palette, font scaling, and message bubble layout density with instant live preview.")
        desc_label.setProperty("subtext", "true")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Theme Group Box
        theme_group = QGroupBox("Theme Selection")
        theme_form = QFormLayout(theme_group)
        theme_form.setContentsMargins(14, 12, 14, 12)
        theme_form.setSpacing(10)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("✨ Eye-Comfort Light Mode (Default)", "light")
        self.theme_combo.addItem("🌙 Deep Slate Dark Mode", "dark")
        self.theme_combo.addItem("🖤 Midnight OLED (Ultra-Dark)", "oled")
        self.theme_combo.addItem("⚡ Cyberpunk Neon", "neon")
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_form.addRow("UI Color Theme:", self.theme_combo)

        layout.addWidget(theme_group)

        # Font & Scaling Group Box
        font_group = QGroupBox("Typography & Scale")
        font_form = QFormLayout(font_group)
        font_form.setContentsMargins(14, 12, 14, 12)
        font_form.setSpacing(10)

        # Font Family
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Segoe UI", "Roboto", "Inter", "Arial", "Consolas", "Fira Code"])
        self.font_combo.currentIndexChanged.connect(self._on_changed)
        font_form.addRow("Font Family:", self.font_combo)

        # Font Scale Slider
        scale_box = QHBoxLayout()
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(80, 140)  # 80% to 140%
        self.scale_slider.setValue(100)
        self.scale_slider.setSingleStep(5)
        self.scale_slider.valueChanged.connect(self._on_scale_changed)

        self.scale_label = QLabel("100%")
        self.scale_label.setFixedWidth(50)
        self.scale_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        scale_box.addWidget(self.scale_slider)
        scale_box.addWidget(self.scale_label)
        font_form.addRow("Font Scale:", scale_box)

        # Density Combo
        self.density_combo = QComboBox()
        self.density_combo.addItem("Comfortable (Standard)", "comfortable")
        self.density_combo.addItem("Compact (High Information)", "compact")
        self.density_combo.currentIndexChanged.connect(self._on_changed)
        font_form.addRow("Layout Density:", self.density_combo)

        layout.addWidget(font_group)
        layout.addStretch()

    def _on_theme_changed(self) -> None:
        theme = self.theme_combo.currentData() or "light"
        self.theme_preview_requested.emit(theme)
        self._on_changed()

    def _on_scale_changed(self, value: int) -> None:
        self.scale_label.setText(f"{value}%")
        self._on_changed()

    def _on_changed(self) -> None:
        self.setting_changed.emit("appearance", self.get_settings())

    def load_settings(self, settings: AppearanceSettings) -> None:
        """Populate UI controls from AppearanceSettings object."""
        self.blockSignals(True)
        t_idx = self.theme_combo.findData(settings.theme)
        if t_idx >= 0:
            self.theme_combo.setCurrentIndex(t_idx)

        f_idx = self.font_combo.findText(settings.font_family)
        if f_idx >= 0:
            self.font_combo.setCurrentIndex(f_idx)

        scale_pct = int(settings.font_scale * 100)
        self.scale_slider.setValue(max(80, min(140, scale_pct)))
        self.scale_label.setText(f"{self.scale_slider.value()}%")

        d_idx = self.density_combo.findData(settings.message_density)
        if d_idx >= 0:
            self.density_combo.setCurrentIndex(d_idx)
        self.blockSignals(False)

    def get_settings(self) -> AppearanceSettings:
        """Return AppearanceSettings object constructed from active UI values."""
        return AppearanceSettings(
            theme=self.theme_combo.currentData() or "light",
            font_family=self.font_combo.currentText(),
            font_scale=self.scale_slider.value() / 100.0,
            message_density=self.density_combo.currentData() or "comfortable",
        )
