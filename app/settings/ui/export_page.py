"""Export settings page widget for Jakariya AI Studio."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.settings.settings_schema import ExportSettingsSchema


class ExportPage(QWidget):
    """Export settings UI page (Formats: PDF, DOCX, HTML, MD, TXT, Paper Size)."""

    setting_changed = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel("Export Preferences")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)

        desc_label = QLabel("Configure default conversation export format, document layout, paper size, and metadata inclusion.")
        desc_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc_label)

        # Export Group
        group = QGroupBox("Document Generation Options")
        form_layout = QFormLayout(group)
        form_layout.setContentsMargins(15, 20, 15, 20)
        form_layout.setSpacing(15)

        self.format_combo = QComboBox()
        self.format_combo.addItem("PDF Document (.pdf)", "pdf")
        self.format_combo.addItem("Word Document (.docx)", "docx")
        self.format_combo.addItem("HTML Document (.html)", "html")
        self.format_combo.addItem("Markdown Document (.md)", "md")
        self.format_combo.addItem("Plain Text (.txt)", "txt")
        self.format_combo.currentIndexChanged.connect(self._on_changed)
        form_layout.addRow("Default Export Format:", self.format_combo)

        self.paper_combo = QComboBox()
        self.paper_combo.addItems(["A4 (Standard ISO)", "Letter (US)", "Legal"])
        self.paper_combo.currentIndexChanged.connect(self._on_changed)
        form_layout.addRow("PDF / DOCX Paper Size:", self.paper_combo)

        self.timestamps_check = QCheckBox("Include timestamps for every message turn")
        self.timestamps_check.toggled.connect(self._on_changed)
        form_layout.addRow("Timestamps:", self.timestamps_check)

        self.attachments_check = QCheckBox("Include image attachments and code blocks in exported documents")
        self.attachments_check.toggled.connect(self._on_changed)
        form_layout.addRow("Attachments:", self.attachments_check)

        layout.addWidget(group)
        layout.addStretch()

    def _on_changed(self) -> None:
        self.setting_changed.emit("export", self.get_settings())

    def load_settings(self, settings: ExportSettingsSchema) -> None:
        self.blockSignals(True)
        idx = self.format_combo.findData(settings.default_format)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)

        p_idx = -1
        for i in range(self.paper_combo.count()):
            txt = self.paper_combo.itemText(i)
            if settings.paper_size and txt.startswith(settings.paper_size):
                p_idx = i
                break
        if p_idx >= 0:
            self.paper_combo.setCurrentIndex(p_idx)

        self.timestamps_check.setChecked(settings.include_timestamps)
        self.attachments_check.setChecked(settings.include_attachments)
        self.blockSignals(False)

    def get_settings(self) -> ExportSettingsSchema:
        raw_text = self.paper_combo.currentText()
        return ExportSettingsSchema(
            default_format=self.format_combo.currentData() or "pdf",
            include_timestamps=self.timestamps_check.isChecked(),
            include_attachments=self.attachments_check.isChecked(),
            paper_size=raw_text or "A4",
        )
