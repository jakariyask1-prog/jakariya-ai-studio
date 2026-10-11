import os
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QFrame,
)

from app.ui.styles import (
    VOICE_BUTTON_LISTENING_STYLE,
    VOICE_BUTTON_BUSY_STYLE,
    VOICE_BUTTON_SPEAKING_STYLE,
    VOICE_BUTTON_ERROR_STYLE,
)
from app.voice import VoiceState


class MessageInputBox(QPlainTextEdit):
    """
    Multi-line auto-resizing text edit widget for chat input (ChatGPT / Gemini style).
    - Auto-expands in height dynamically as user types lines (up to max_height).
    - Auto-scrolls smoothly to keep cursor in view when text exceeds max_height.
    - Pressing Enter sends the message.
    - Shift+Enter or Ctrl+Enter inserts a new line.
    """

    returnPressed = Signal()

    def __init__(self, parent=None, min_height: int = 44, max_height: int = 160):
        super().__init__(parent)
        self._min_height = min_height
        self._max_height = max_height

        self.document().setDocumentMargin(3.0)
        self.setPlaceholderText("Message Jakariya AI Studio or choose a suggested prompt...")
        self.setMinimumWidth(80)
        self.setMinimumHeight(self._min_height)
        self.setMaximumHeight(self._max_height)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.textChanged.connect(self.adjust_height)
        self.cursorPositionChanged.connect(self.ensureCursorVisible)
        self.adjust_height()

    def adjust_height(self):
        doc = self.document()
        block = doc.firstBlock()
        total_lines = 0
        while block.isValid():
            layout = block.layout()
            if layout and layout.lineCount() > 0:
                total_lines += layout.lineCount()
            else:
                total_lines += 1
            block = block.next()

        if total_lines == 0:
            total_lines = 1

        fm = self.fontMetrics()
        line_height = fm.lineSpacing()
        doc_margin = int(doc.documentMargin() * 2)
        margins = self.contentsMargins()
        vertical_padding = 16

        total_height = (total_lines * line_height) + doc_margin + margins.top() + margins.bottom() + vertical_padding
        clamped_height = max(self._min_height, min(total_height, self._max_height))
        self.setFixedHeight(clamped_height)
        self.ensureCursorVisible()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_height()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not (event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
                self.returnPressed.emit()
                event.accept()
                return
        super().keyPressEvent(event)
        self.ensureCursorVisible()

    def text(self) -> str:
        """Alias for toPlainText() for backward compatibility."""
        return self.toPlainText()

    def setText(self, text: str) -> None:
        """Alias for setPlainText() for backward compatibility."""
        self.setPlainText(text)
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.adjust_height()
        self.ensureCursorVisible()

    def clear(self) -> None:
        super().clear()
        self.adjust_height()


class InputBar(QWidget):
    """
    Elevated Floating Input Capsule (ChatGPT & Claude & Gemini Style).

    Responsible for collecting user input (text, attachments, voice)
    and notifying the main window.
    """

    send_requested = Signal(str)
    attach_requested = Signal()
    folder_requested = Signal()
    workspace_cleared = Signal()
    attachment_remove_requested = Signal(int)
    voice_requested = Signal()
    live_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(54)
        self._active_workspace_path = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 0, 10, 2)
        outer_layout.setSpacing(2)

        # Voice status indicator (shown above input bar when active)
        self.voice_status_label = QLabel("")
        self.voice_status_label.setFixedHeight(20)
        self.voice_status_label.setStyleSheet("color: #4F46E5; font-weight: 600; padding: 0px 4px; font-size: 8.5pt;")
        self.voice_status_label.setVisible(False)
        
        # Thinking animation timer
        self._thinking_timer = QTimer(self)
        self._thinking_timer.timeout.connect(self._animate_thinking)
        self._thinking_dots = 0
        
        # Speaking animation timer
        self._speaking_timer = QTimer(self)
        self._speaking_timer.timeout.connect(self._animate_speaking)
        self._speaking_icon_state = 0
        self._is_speaking = False

        # Active Workspace Indicator Widget (Antigravity mode)
        self.workspace_widget = QWidget()
        self.workspace_layout = QHBoxLayout(self.workspace_widget)
        self.workspace_layout.setContentsMargins(2, 0, 2, 2)
        self.workspace_layout.setSpacing(4)
        self.workspace_widget.setVisible(False)

        # Attachment Chips Area (shown above capsule)
        self.attachments_widget = QWidget()
        self.attachments_layout = QHBoxLayout(self.attachments_widget)
        self.attachments_layout.setContentsMargins(2, 0, 2, 2)
        self.attachments_layout.setSpacing(4)
        self.attachments_widget.setVisible(False)

        # Elevated Floating Input Capsule Frame
        self.capsule_frame = QFrame()
        self.capsule_frame.setObjectName("inputCapsule")

        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        self.capsule_shadow = QGraphicsDropShadowEffect(self)
        self.capsule_shadow.setBlurRadius(16)
        self.capsule_shadow.setOffset(0, 3)
        self.capsule_shadow.setColor(QColor(15, 23, 42, 14))
        self.capsule_frame.setGraphicsEffect(self.capsule_shadow)

        capsule_layout = QHBoxLayout(self.capsule_frame)
        capsule_layout.setContentsMargins(5, 3, 5, 3)
        capsule_layout.setSpacing(6)

        # 1. Integrated Paperclip Attach File Button
        self.attach_button = QToolButton()
        self.attach_button.setText("⊕")
        self.attach_button.setFixedSize(34, 34)
        self.attach_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_button.setToolTip("Attach files or documents (PDF, DOCX, Images, Text)")
        self.attach_button.clicked.connect(self.attach_requested)

        # 1b. Project Workspace Folder Button (Antigravity Mode)
        self.folder_button = QToolButton()
        self.folder_button.setText("📁")
        self.folder_button.setFixedSize(34, 34)
        self.folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_button.setToolTip("Select Project Folder / Workspace (Antigravity Mode)")
        self.folder_button.clicked.connect(self.folder_requested)

        # 2. Main Message QPlainTextEdit Multi-line Text Field
        self.message_input = MessageInputBox(min_height=44, max_height=160)
        self.message_input.setPlaceholderText("Message Jakariya AI Studio or choose a suggested prompt...")
        self.message_input.returnPressed.connect(self.send_message)

        # 3. Autonomous AI Agent Mode Toggle Pill
        self.agent_button = QPushButton("✧ Agent Mode")
        self.agent_button.setFixedHeight(34)
        self.agent_button.setCheckable(True)
        self.agent_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.agent_button.setToolTip("Toggle Autonomous AI Agent Mode (multi-step reasoning & tool execution)")

        # 4. Live Conversation Toggle Pill
        self.live_button = QPushButton("◉ Live Mode")
        self.live_button.setFixedHeight(34)
        self.live_button.setCheckable(True)
        self.live_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.live_button.setToolTip("Start Live Conversation (continuous voice mode)")
        self.live_button.clicked.connect(self.live_requested.emit)

        # 5. Voice Microphone Button
        self.voice_button = QPushButton("🎙")
        self.voice_button.setFixedSize(34, 34)
        self.voice_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.voice_button.setToolTip("Start voice input")
        self.voice_button.clicked.connect(self.voice_requested.emit)

        # 6. Primary Circular Send Button
        self.send_button = QPushButton("↑")
        self.send_button.setFixedSize(34, 34)
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setToolTip("Send message (Enter)")
        self.send_button.clicked.connect(self.send_message)

        # Assemble Capsule Components
        capsule_layout.addWidget(self.attach_button, 0, Qt.AlignmentFlag.AlignBottom)
        capsule_layout.addWidget(self.folder_button, 0, Qt.AlignmentFlag.AlignBottom)
        capsule_layout.addWidget(self.message_input, 1)
        capsule_layout.addWidget(self.agent_button, 0, Qt.AlignmentFlag.AlignBottom)
        capsule_layout.addWidget(self.live_button, 0, Qt.AlignmentFlag.AlignBottom)
        capsule_layout.addWidget(self.voice_button, 0, Qt.AlignmentFlag.AlignBottom)
        capsule_layout.addWidget(self.send_button, 0, Qt.AlignmentFlag.AlignBottom)

        # Assembly to Outer Layout
        outer_layout.addWidget(self.voice_status_label)
        outer_layout.addWidget(self.workspace_widget)
        outer_layout.addWidget(self.attachments_widget)
        outer_layout.addWidget(self.capsule_frame)

        self._theme = "light"
        self._is_compact = False
        self.apply_theme("light")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w = self.width()
        if w < 520:
            self._is_compact = True
            self.agent_button.setText("✧")
            self.agent_button.setFixedWidth(32)
            self.live_button.setText("◉")
            self.live_button.setFixedWidth(32)
        elif w < 680:
            self._is_compact = True
            self.agent_button.setText("✧ Agent")
            self.agent_button.setMinimumWidth(0)
            self.agent_button.setMaximumWidth(16777215)
            self.live_button.setText("◉ Live")
            self.live_button.setMinimumWidth(0)
            self.live_button.setMaximumWidth(16777215)
        else:
            self._is_compact = False
            self.agent_button.setText("✧ Agent Mode")
            self.agent_button.setMinimumWidth(0)
            self.agent_button.setMaximumWidth(16777215)
            self.live_button.setText("◉ Live Mode")
            self.live_button.setMinimumWidth(0)
            self.live_button.setMaximumWidth(16777215)

    def apply_theme(self, theme_name: str) -> None:
        """Update input capsule and button styles dynamically for active theme."""
        self._theme = theme_name
        from app.ui.styles import get_theme_palette, get_voice_button_ready_style
        p = get_theme_palette(theme_name)

        send_bg = "#10A37F" if theme_name in ("light", "dark", "oled") else "#F472B6"
        send_hover = "#0D8A6C" if theme_name in ("light", "dark", "oled") else "#DB2777"
        checked_pill_bg = "#10A37F" if theme_name in ("light", "dark", "oled") else "#F472B6"

        is_dark = theme_name in ("dark", "oled", "neon")
        if hasattr(self, "capsule_shadow"):
            if is_dark:
                self.capsule_shadow.setBlurRadius(20)
                self.capsule_shadow.setOffset(0, 4)
                self.capsule_shadow.setColor(QColor(0, 0, 0, 90))
            else:
                self.capsule_shadow.setBlurRadius(16)
                self.capsule_shadow.setOffset(0, 3)
                self.capsule_shadow.setColor(QColor(15, 23, 42, 14))

        self.capsule_frame.setStyleSheet(f"""
            QFrame#inputCapsule {{
                background-color: {p['bg_capsule']};
                border: 1px solid {p['border_capsule']};
                border-radius: 24px;
                padding: 4px 8px;
            }}
            QFrame#inputCapsule:focus-within {{
                border-color: {p['border_capsule_focus']};
            }}
        """)

        self.message_input.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: transparent;
                background: transparent;
                color: {p['input_text']};
                border: none;
                font-size: 11pt;
                font-family: 'Segoe UI Variable', 'Noto Sans Bengali', 'Inter', sans-serif;
                padding: 4px 6px;
                selection-background-color: #818CF8;
                selection-color: #FFFFFF;
            }}
            QPlainTextEdit QScrollBar:vertical {{
                width: 6px;
                background: transparent;
                margin: 4px 0px 4px 0px;
            }}
            QPlainTextEdit QScrollBar::handle:vertical {{
                background: {p['border_capsule']};
                min-height: 20px;
                border-radius: 3px;
            }}
            QPlainTextEdit QScrollBar::handle:vertical:hover {{
                background: {p['border_capsule_focus']};
            }}
            QPlainTextEdit QScrollBar::add-line:vertical,
            QPlainTextEdit QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QPlainTextEdit QScrollBar::add-page:vertical,
            QPlainTextEdit QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)

        palette = self.message_input.palette()
        palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.transparent)
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(p['placeholder_text']))
        palette.setColor(QPalette.ColorRole.Text, QColor(p['input_text']))
        self.message_input.setPalette(palette)

        tool_btn_style = f"""
            QToolButton {{
                background-color: {p['btn_secondary_bg']};
                color: {p['btn_secondary_text']};
                border: 1px solid {p['btn_secondary_border']};
                border-radius: 17px;
                font-size: 12pt;
            }}
            QToolButton:hover {{
                background-color: {p['btn_secondary_hover']};
                color: {p['input_text']};
                border-color: {p['border_capsule_focus']};
            }}
        """
        self.attach_button.setStyleSheet(tool_btn_style)
        self.folder_button.setStyleSheet(tool_btn_style)

        pill_btn_style = f"""
            QPushButton {{
                background-color: {p['btn_secondary_bg']};
                color: {p['btn_secondary_text']};
                border: 1px solid {p['btn_secondary_border']};
                border-radius: 14px;
                padding: 0px 10px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                background-color: {p['btn_secondary_hover']};
                color: {p['input_text']};
                border-color: {p['border_capsule_focus']};
            }}
            QPushButton:checked {{
                background-color: {checked_pill_bg};
                color: #FFFFFF;
                border: 1px solid {checked_pill_bg};
                font-weight: 700;
            }}
        """
        self.agent_button.setStyleSheet(pill_btn_style)
        self.live_button.setStyleSheet(pill_btn_style)
        if not self.voice_button.text() or self.voice_button.text() == "🎙":
            self.voice_button.setStyleSheet(get_voice_button_ready_style(theme_name))

        self.send_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {send_bg};
                color: #FFFFFF;
                border: none;
                border-radius: 17px;
                font-size: 13pt;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {send_hover}; }}
            QPushButton:disabled {{ background-color: {p['btn_secondary_bg']}; color: {p['placeholder_text']}; }}
        """)

    # ---------------------------------

    def set_voice_state(self, state: VoiceState) -> None:
        """Update voice UI elements dynamically based on the current VoiceState."""
        self._thinking_timer.stop()
        self._speaking_timer.stop()
        self._is_speaking = False
        
        if state != VoiceState.LISTENING and hasattr(self, "voice_shadow"):
            self.voice_shadow.setBlurRadius(0)
            self.voice_shadow.setColor(QColor(0, 0, 0, 0))

        from app.ui.styles import get_voice_button_ready_style
        ready_style = get_voice_button_ready_style(getattr(self, "_theme", "light"))

        if state == VoiceState.READY:
            self.voice_button.setText("🎙")
            self.voice_button.setToolTip("Start voice input")
            self.voice_button.setEnabled(True)
            self.voice_button.setStyleSheet(ready_style)
            self.voice_status_label.setVisible(False)
        elif state == VoiceState.LISTENING:
            self.voice_button.setText("◉")
            self.voice_button.setToolTip("Stop listening")
            self.voice_button.setEnabled(True)
            self.voice_button.setStyleSheet(VOICE_BUTTON_LISTENING_STYLE)
            self.voice_status_label.setText("🎙️ Listening...")
            self.voice_status_label.setStyleSheet("color: #EF4444; font-weight: 600; padding: 2px 6px;")
            self.voice_status_label.setVisible(True)
        elif state == VoiceState.TRANSCRIBING:
            self.voice_button.setText("⏳")
            self.voice_button.setToolTip("Transcribing audio...")
            self.voice_button.setEnabled(False)
            self.voice_button.setStyleSheet(VOICE_BUTTON_BUSY_STYLE)
            self.voice_status_label.setText("⚙️ Transcribing...")
            self.voice_status_label.setStyleSheet("color: #F59E0B; font-weight: 600; padding: 2px 6px;")
            self.voice_status_label.setVisible(True)
        elif state == VoiceState.THINKING:
            self.voice_button.setText("🧠")
            self.voice_button.setToolTip("AI Thinking...")
            self.voice_button.setEnabled(False)
            self.voice_button.setStyleSheet(VOICE_BUTTON_BUSY_STYLE)
            self.voice_status_label.setText("💭 Thinking")
            self.voice_status_label.setStyleSheet("color: #F59E0B; font-weight: 600; padding: 2px 6px;")
            self.voice_status_label.setVisible(True)
            self._thinking_dots = 0
            self._thinking_timer.start(400)
        elif state == VoiceState.SPEAKING:
            self.voice_button.setText("🔊")
            self.voice_button.setToolTip("Click to interrupt speaking")
            self.voice_button.setEnabled(True)
            self.voice_button.setStyleSheet(VOICE_BUTTON_SPEAKING_STYLE)
            self.voice_status_label.setText("🔊 Speaking...")
            self.voice_status_label.setStyleSheet("color: #10B981; font-weight: 600; padding: 2px 6px;")
            self.voice_status_label.setVisible(True)
            self._is_speaking = True
            self._speaking_icon_state = 0
            self._speaking_timer.start(250)
        elif state == VoiceState.INTERRUPTED:
            self.voice_button.setText("🎙")
            self.voice_button.setToolTip("Voice interrupted. Click to reset")
            self.voice_button.setEnabled(True)
            self.voice_button.setStyleSheet(ready_style)
            self.voice_status_label.setText("⏹️ Interrupted")
            self.voice_status_label.setStyleSheet("color: #64748B; font-weight: 600; padding: 2px 6px;")
            self.voice_status_label.setVisible(True)
        elif state == VoiceState.ERROR:
            self.voice_button.setText("⚠️")
            self.voice_button.setToolTip("Voice error. Click to reset")
            self.voice_button.setEnabled(True)
            self.voice_button.setStyleSheet(VOICE_BUTTON_ERROR_STYLE)
            self.voice_status_label.setText("⚠️ Voice error")
            self.voice_status_label.setStyleSheet("color: #DC2626; font-weight: 600; padding: 2px 6px;")
            self.voice_status_label.setVisible(True)

    def is_agent_mode_active(self) -> bool:
        """Return True if user enabled Autonomous AI Agent Mode."""
        return self.agent_button.isChecked()

    def set_live_mode(self, active: bool) -> None:
        """Update Live button visual state."""
        self.live_button.setChecked(active)
        if active:
            self.live_button.setText("🛑 Stop Live")
            self.live_button.setToolTip("Stop Live Conversation")
            self.voice_status_label.setText("Live Conversation Active")
            self.voice_status_label.setStyleSheet("color: #10B981; font-weight: 700; padding: 2px 6px;")
            self.voice_status_label.setVisible(True)
        else:
            self.live_button.setText("◉ Live Mode")
            self.live_button.setToolTip("Start Live Conversation (continuous voice mode)")

    def _animate_thinking(self):
        """Animates the thinking label with dots."""
        self._thinking_dots = (self._thinking_dots + 1) % 4
        dots = "." * self._thinking_dots
        self.voice_status_label.setText(f"💭 Thinking{dots}")

    def _animate_speaking(self):
        """Animates the speaker icon while TTS plays."""
        if not self._is_speaking:
            return
        icons = ["🔈", "🔉", "🔊"]
        self._speaking_icon_state = (self._speaking_icon_state + 1) % 3
        icon = icons[self._speaking_icon_state]
        self.voice_button.setText(icon)
        self.voice_status_label.setText(f"{icon} Speaking...")

    def update_mic_level(self, level: float):
        """Visually indicate microphone volume level during listening."""
        if self.voice_button.text() != "◉":
            return
        intensity = min(int(level * 10 * 255), 255)
        bg_color = f"rgba(239, 68, 68, {0.2 + (intensity/255)*0.8})"
        dynamic_style = VOICE_BUTTON_LISTENING_STYLE + f"QPushButton {{ background-color: {bg_color}; border-color: #DC2626; }}"
        self.voice_button.setStyleSheet(dynamic_style)

    def set_playing_state(self, is_playing: bool):
        """Control the speaking animation based on the audio player's actual playing state."""
        if self.voice_button.text() not in ("🔈", "🔉", "🔊"):
            return
            
        if is_playing and not self._speaking_timer.isActive():
            self._is_speaking = True
            self._speaking_timer.start(250)
        elif not is_playing and self._speaking_timer.isActive():
            self._is_speaking = False
            self._speaking_timer.stop()
            self.voice_button.setText("🔊")
            self.voice_status_label.setText("🔊 Speaking...")

    def send_message(self):
        message = self.message_input.text().strip()
        if not message:
            return
        self.send_requested.emit(message)
        self.message_input.clear()
        self.message_input.setFocus()

    def enable(self):
        self.message_input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.attach_button.setEnabled(True)
        self.folder_button.setEnabled(True)
        self.voice_button.setEnabled(True)

    def disable(self):
        self.message_input.setEnabled(False)
        self.send_button.setEnabled(False)
        self.attach_button.setEnabled(False)
        self.folder_button.setEnabled(False)
        self.voice_button.setEnabled(False)

    def set_workspace_folder(self, folder_path: str | None) -> None:
        """Set active project workspace folder and show a clearable chip."""
        self.clear_workspace_folder()
        if not folder_path:
            return
        folder_str = str(folder_path).strip()
        if not folder_str or not os.path.isdir(folder_str):
            return
        self._active_workspace_path = folder_str
        folder_name = os.path.basename(folder_str.rstrip("/\\")) or folder_str
        chip = QToolButton()
        chip.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        chip.setText(f"📁 Workspace: {folder_name}  ×")
        chip.setToolTip(f"Active Project Workspace:\n{folder_str}\n\nClick × to disconnect workspace")
        chip.setStyleSheet(
            "QToolButton { background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; "
            "border-radius: 8px; padding: 4px 10px; font-weight: 600; font-size: 9pt; } "
            "QToolButton:hover { background: #D1FAE5; color: #047857; }"
        )
        chip.clicked.connect(self._on_workspace_chip_clicked)
        self.workspace_layout.addWidget(chip)
        self.workspace_layout.addStretch(1)
        self.workspace_widget.setVisible(True)
        # Automatically enable Agent Mode for project workspace tasks
        self.agent_button.setChecked(True)

    def clear_workspace_folder(self) -> None:
        """Clear active project workspace folder."""
        self._active_workspace_path = None
        while self.workspace_layout.count():
            item = self.workspace_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.workspace_widget.setVisible(False)

    def _on_workspace_chip_clicked(self) -> None:
        self.clear_workspace_folder()
        self.workspace_cleared.emit()

    def get_active_workspace(self) -> str | None:
        return self._active_workspace_path

    def clear(self):
        self.message_input.clear()

    def set_attachments(self, files: list[object]):
        self.clear_attachments()
        if not files:
            self.clear_attachments()
            return
        for index, uploaded_file in enumerate(files):
            name = str(getattr(uploaded_file, "original_name", "Attachment"))
            is_image = bool(getattr(uploaded_file, "is_image_file", False))
            chip = QToolButton()
            chip.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            chip.setText(f"{'🖼' if is_image else '📎'} {name}  ×")
            chip.setToolTip(f"Remove {name}")
            chip.setStyleSheet(
                "QToolButton { background:#EEF2FF; color:#3730A3; border:1px solid #C7D2FE; "
                "border-radius:8px; padding:4px 10px; font-weight:600; } QToolButton:hover { background:#E0E7FF; }"
            )
            chip.clicked.connect(lambda _checked=False, i=index: self.attachment_remove_requested.emit(i))
            self.attachments_layout.addWidget(chip)
        self.attachments_layout.addStretch(1)
        self.attachments_widget.setVisible(True)
        if not self.message_input.text().strip():
            self.message_input.setText("Analyze the attached file.")

    def clear_attachments(self):
        while self.attachments_layout.count():
            item = self.attachments_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.attachments_widget.setVisible(False)

    def focus_input(self):
        self.message_input.setFocus()
