"""Chat and AI Persona settings page widget for Jakariya AI Studio."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.settings.settings_schema import ChatSettingsSchema


class ChatPage(QWidget):
    """Chat & Persona settings UI page (Personas, User Profile, Temperature, Tokens)."""

    setting_changed = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel("Chat & AI Persona Settings")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)

        desc_label = QLabel("Configure AI system personas, custom system instructions, memory context, and generation hyper-parameters.")
        desc_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc_label)

        # Persona Group
        p_group = QGroupBox("AI Assistant Persona & System Instruction")
        p_form = QFormLayout(p_group)
        p_form.setContentsMargins(15, 20, 15, 20)
        p_form.setSpacing(12)

        self.persona_combo = QComboBox()
        self.persona_combo.addItem("Jakariya AI Studio Assistant (Default)", "default")
        self.persona_combo.addItem("Mathematics & Scientific Research Tutor", "math_tutor")
        self.persona_combo.addItem("Software Architect & Code Master", "code_expert")
        self.persona_combo.addItem("Custom Persona (Enter System Prompt Below)", "custom")
        self.persona_combo.currentIndexChanged.connect(self._on_persona_changed)
        p_form.addRow("Active Persona:", self.persona_combo)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Enter custom system prompt instruction...")
        self.prompt_edit.setMaximumHeight(90)
        self.prompt_edit.textChanged.connect(self._on_changed)
        p_form.addRow("Custom Instruction:", self.prompt_edit)

        self.profile_check = QCheckBox("Inject User Profile memory context into conversation system prompt")
        self.profile_check.toggled.connect(self._on_changed)
        p_form.addRow("User Profile Memory:", self.profile_check)

        layout.addWidget(p_group)

        # Hyper-parameters Group
        param_group = QGroupBox("Generation Hyper-parameters")
        param_form = QFormLayout(param_group)
        param_form.setContentsMargins(15, 20, 15, 20)
        param_form.setSpacing(12)

        # Temperature
        temp_box = QHBoxLayout()
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 20)  # 0.0 to 2.0
        self.temp_slider.setValue(7)
        self.temp_slider.valueChanged.connect(self._on_temp_changed)

        self.temp_label = QLabel("0.70")
        self.temp_label.setFixedWidth(50)
        self.temp_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        temp_box.addWidget(self.temp_slider)
        temp_box.addWidget(self.temp_label)
        param_form.addRow("Temperature (Creativity):", temp_box)

        # Max Tokens
        token_box = QHBoxLayout()
        self.token_slider = QSlider(Qt.Orientation.Horizontal)
        self.token_slider.setRange(256, 8192)
        self.token_slider.setValue(2048)
        self.token_slider.setSingleStep(256)
        self.token_slider.valueChanged.connect(self._on_token_changed)

        self.token_label = QLabel("2048")
        self.token_label.setFixedWidth(50)
        self.token_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        token_box.addWidget(self.token_slider)
        token_box.addWidget(self.token_label)
        param_form.addRow("Max Token Response:", token_box)

        # Max History Turns
        history_box = QHBoxLayout()
        self.history_slider = QSlider(Qt.Orientation.Horizontal)
        self.history_slider.setRange(5, 100)
        self.history_slider.setValue(20)
        self.history_slider.setSingleStep(1)
        self.history_slider.valueChanged.connect(self._on_history_turns_changed)

        self.history_label = QLabel("20")
        self.history_label.setFixedWidth(50)
        self.history_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        history_box.addWidget(self.history_slider)
        history_box.addWidget(self.history_label)
        param_form.addRow("Max History Turns:", history_box)

        layout.addWidget(param_group)
        layout.addStretch()

    def _on_persona_changed(self) -> None:
        is_custom = self.persona_combo.currentData() == "custom"
        self.prompt_edit.setEnabled(is_custom)
        self._on_changed()

    def _on_temp_changed(self, val: int) -> None:
        self.temp_label.setText(f"{val / 10.0:.2f}")
        self._on_changed()

    def _on_token_changed(self, val: int) -> None:
        self.token_label.setText(str(val))
        self._on_changed()

    def _on_history_turns_changed(self, val: int) -> None:
        self.history_label.setText(str(val))
        self._on_changed()

    def _on_changed(self) -> None:
        self.setting_changed.emit("chat", self.get_settings())

    def load_settings(self, settings: ChatSettingsSchema) -> None:
        self.blockSignals(True)
        idx = self.persona_combo.findData(settings.system_persona)
        if idx >= 0:
            self.persona_combo.setCurrentIndex(idx)

        self.prompt_edit.setText(settings.custom_system_prompt)
        self.prompt_edit.setEnabled(settings.system_persona == "custom")
        self.profile_check.setChecked(settings.attach_user_profile)

        t_val = int(settings.temperature * 10)
        self.temp_slider.setValue(max(0, min(20, t_val)))
        self.temp_label.setText(f"{settings.temperature:.2f}")

        self.token_slider.setValue(settings.max_tokens)
        self.token_label.setText(str(settings.max_tokens))

        self.history_slider.setValue(settings.max_history_turns)
        self.history_label.setText(str(settings.max_history_turns))
        self.blockSignals(False)

    def get_settings(self) -> ChatSettingsSchema:
        return ChatSettingsSchema(
            system_persona=self.persona_combo.currentData() or "default",
            custom_system_prompt=self.prompt_edit.toPlainText().strip(),
            attach_user_profile=self.profile_check.isChecked(),
            max_history_turns=self.history_slider.value(),
            temperature=self.temp_slider.value() / 10.0,
            max_tokens=self.token_slider.value(),
        )
