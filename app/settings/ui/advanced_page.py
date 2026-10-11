"""Advanced maintenance and diagnostics settings page widget for Jakariya AI Studio."""

from __future__ import annotations

import logging
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.settings.settings_schema import AdvancedSettingsSchema
from app.utils.paths import get_uploaded_files_dir, get_generated_images_dir


class AdvancedPage(QWidget):
    """Advanced settings UI page (Logging, Orphan file cleanup, Cache maintenance)."""

    setting_changed = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel("Advanced Maintenance & Diagnostics")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)

        desc_label = QLabel("Configure system diagnostics, orphan file cleanup rules, and local cache maintenance.")
        desc_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc_label)

        # Logging Group
        log_group = QGroupBox("System Logging & Maintenance")
        log_form = QFormLayout(log_group)
        log_form.setContentsMargins(15, 20, 15, 20)
        log_form.setSpacing(15)

        self.log_combo = QComboBox()
        self.log_combo.addItems(["INFO", "DEBUG", "WARNING", "ERROR"])
        self.log_combo.currentIndexChanged.connect(self._on_changed)
        log_form.addRow("Diagnostic Log Level:", self.log_combo)

        self.sweep_check = QCheckBox("Automatically sweep unreferenced upload assets on app exit")
        self.sweep_check.toggled.connect(self._on_changed)
        log_form.addRow("Orphan Asset Sweep:", self.sweep_check)

        layout.addWidget(log_group)

        # Actions Group
        action_group = QGroupBox("Cache & Storage Actions")
        action_layout = QVBoxLayout(action_group)
        action_layout.setContentsMargins(15, 20, 15, 20)
        action_layout.setSpacing(12)

        # Cache Limit Slider
        cache_form = QFormLayout()
        cache_form.setContentsMargins(0, 0, 0, 10)
        cache_form.setSpacing(12)

        cache_box = QHBoxLayout()
        self.cache_slider = QSlider(Qt.Orientation.Horizontal)
        self.cache_slider.setRange(100, 5000)  # 100 MB to 5000 MB
        self.cache_slider.setValue(500)
        self.cache_slider.setSingleStep(50)
        self.cache_slider.valueChanged.connect(self._on_cache_slider_changed)

        self.cache_label = QLabel("500 MB")
        self.cache_label.setFixedWidth(60)
        self.cache_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        cache_box.addWidget(self.cache_slider)
        cache_box.addWidget(self.cache_label)
        cache_form.addRow("Cache Size Limit:", cache_box)
        action_layout.addLayout(cache_form)

        btn_box = QHBoxLayout()
        self.btn_clear_cache = QPushButton("🧹 Clear Temp Cache")
        self.btn_clear_cache.setStyleSheet("background-color: #374151; color: #E5E7EB; padding: 6px 14px; border-radius: 6px;")
        self.btn_clear_cache.clicked.connect(self._clear_cache)
        btn_box.addWidget(self.btn_clear_cache)

        self.cache_status_label = QLabel("Ready")
        self.cache_status_label.setStyleSheet("color: #888888; font-size: 12px;")
        btn_box.addWidget(self.cache_status_label)
        btn_box.addStretch()

        action_layout.addLayout(btn_box)
        layout.addWidget(action_group)
        layout.addStretch()

    def _clear_cache(self) -> None:
        import shutil
        deleted_count = 0
        for directory_func in [get_uploaded_files_dir, get_generated_images_dir]:
            try:
                path = directory_func()
                if path.exists() and path.is_dir():
                    for item in path.iterdir():
                        if item.is_file() or item.is_symlink():
                            try:
                                item.unlink()
                                deleted_count += 1
                            except Exception as e:
                                logging.warning(f"[AdvancedPage] Failed to delete file {item}: {e}")
                        elif item.is_dir():
                            try:
                                shutil.rmtree(item)
                                deleted_count += 1
                            except Exception as e:
                                logging.warning(f"[AdvancedPage] Failed to delete folder {item}: {e}")
            except Exception as e:
                logging.warning(f"[AdvancedPage] Error clearing directory: {e}")

        self.cache_status_label.setText(f"Cache cleared successfully! ({deleted_count} files removed)")
        self.cache_status_label.setStyleSheet("color: #10B981; font-weight: bold;")

    def _on_cache_slider_changed(self, val: int) -> None:
        self.cache_label.setText(f"{val} MB")
        self._on_changed()

    def _on_changed(self) -> None:
        self.setting_changed.emit("advanced", self.get_settings())

    def load_settings(self, settings: AdvancedSettingsSchema) -> None:
        self.blockSignals(True)
        idx = self.log_combo.findText(settings.log_level)
        if idx >= 0:
            self.log_combo.setCurrentIndex(idx)

        self.sweep_check.setChecked(settings.auto_sweep_orphans)
        self.cache_slider.setValue(settings.cache_limit_mb)
        self.cache_label.setText(f"{settings.cache_limit_mb} MB")
        self.blockSignals(False)

    def get_settings(self) -> AdvancedSettingsSchema:
        return AdvancedSettingsSchema(
            log_level=self.log_combo.currentText(),
            auto_sweep_orphans=self.sweep_check.isChecked(),
            cache_limit_mb=self.cache_slider.value(),
        )
