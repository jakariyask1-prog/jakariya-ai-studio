"""
app/ui/status_bar.py — Jakariya AI Studio Custom Status Bar Widget.

Provides a styled QStatusBar subclass with:
- A permanent left-aligned status message label
- A permanent right-aligned model badge pill
- Animated fade-in/fade-out for transient messages
- Color-coded severity (info / success / warning / error)
"""

from __future__ import annotations

import logging
from enum import Enum

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QLabel, QStatusBar, QWidget, QHBoxLayout

logger = logging.getLogger(__name__)


class MessageSeverity(Enum):
    """Visual severity level for status messages."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


# Severity → background/text color pairs
_SEVERITY_STYLES: dict[MessageSeverity, tuple[str, str]] = {
    MessageSeverity.INFO:    ("#F1F5F9", "#334155"),   # slate-100 / slate-700
    MessageSeverity.SUCCESS: ("#DCFCE7", "#166534"),   # green-100 / green-800
    MessageSeverity.WARNING: ("#FEF9C3", "#854D0E"),   # yellow-100 / yellow-800
    MessageSeverity.ERROR:   ("#FEE2E2", "#991B1B"),   # red-100 / red-800
}

# Duration (ms) before a transient message reverts to the idle message
_TRANSIENT_DURATION_MS = 4000


class AppStatusBar(QStatusBar):
    """
    Custom application status bar with model badge and severity colouring.

    Usage::

        bar = AppStatusBar(parent=self)
        self.setStatusBar(bar)
        bar.show_message("Exporting…", severity=MessageSeverity.INFO)
        bar.show_message("Export done!", severity=MessageSeverity.SUCCESS)
        bar.show_error("Connection failed")
        bar.set_model_badge("gemini-2.5-flash")
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(False)

        self._idle_message: str = "Ready"

        # ── Left: status message label ──────────────────────────────────────
        self._msg_label = QLabel(self._idle_message, self)
        self._msg_label.setObjectName("statusMsgLabel")
        self._msg_label.setStyleSheet(
            "color: #475569; font-size: 10pt; padding: 0 6px;"
        )

        # ── Right: model badge pill ─────────────────────────────────────────
        self._badge_widget = QWidget(self)
        badge_layout = QHBoxLayout(self._badge_widget)
        badge_layout.setContentsMargins(0, 2, 6, 2)
        badge_layout.setSpacing(0)

        self._badge_label = QLabel("", self._badge_widget)
        self._badge_label.setObjectName("modelBadgeLabel")
        self._badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge_label.setStyleSheet(
            "background-color: #EEF2FF; color: #4F46E5; border: 1px solid #C7D2FE; "
            "border-radius: 10px; padding: 2px 10px; font-size: 9pt; font-weight: 600;"
        )
        badge_layout.addWidget(self._badge_label)

        # Add widgets to the Qt status bar
        self.addWidget(self._msg_label, 1)          # stretches to fill available space
        self.addPermanentWidget(self._badge_widget)  # pinned to the right

        # Revert timer: restores idle message after transient duration
        self._revert_timer = QTimer(self)
        self._revert_timer.setSingleShot(True)
        self._revert_timer.timeout.connect(self._revert_to_idle)

        self.apply_theme("light")

    def apply_theme(self, theme_name: str) -> None:
        """Update status bar container and model badge styling according to active theme."""
        self._current_theme = theme_name
        from app.ui.styles import get_theme_palette
        p = get_theme_palette(theme_name)
        self.setStyleSheet(
            f"QStatusBar {{"
            f"  background-color: {p['status_bg']};"
            f"  border-top: 1px solid {p['status_border']};"
            f"  min-height: 28px;"
            f"  max-height: 28px;"
            f"}}"
            f"QStatusBar::item {{ border: none; }}"
        )
        self._msg_label.setStyleSheet(
            f"color: {p['status_text']}; font-size: 10pt; padding: 0 6px;"
        )
        is_dark = str(theme_name).lower() in ("dark", "oled", "neon")
        badge_bg = "#312E81" if is_dark else "#EEF2FF"
        badge_fg = "#C7D2FE" if is_dark else "#4F46E5"
        badge_border = "#4338CA" if is_dark else "#C7D2FE"
        self._badge_label.setStyleSheet(
            f"background-color: {badge_bg}; color: {badge_fg}; border: 1px solid {badge_border}; "
            f"border-radius: 10px; padding: 2px 10px; font-size: 9pt; font-weight: 600;"
        )


    # ── Public API ──────────────────────────────────────────────────────────


    def show_message(
        self,
        message: str,
        severity: MessageSeverity = MessageSeverity.INFO,
        transient: bool = True,
    ) -> None:
        """Display *message* on the status bar with optional colour coding.

        Args:
            message:   Text to display.
            severity:  Colour theme (INFO / SUCCESS / WARNING / ERROR).
            transient: If True the message auto-reverts to the idle text after
                       ``_TRANSIENT_DURATION_MS`` milliseconds.
        """
        is_dark = str(getattr(self, "_current_theme", "light")).lower() in ("dark", "oled", "neon")
        if is_dark:
            _dark_styles = {
                MessageSeverity.INFO:    ("#1E293B", "#94A3B8"),
                MessageSeverity.SUCCESS: ("#064E3B", "#34D399"),
                MessageSeverity.WARNING: ("#78350F", "#FBBF24"),
                MessageSeverity.ERROR:   ("#7F1D1D", "#F87171"),
            }
            bg, fg = _dark_styles.get(severity, ("#1E293B", "#94A3B8"))
        else:
            bg, fg = _SEVERITY_STYLES.get(severity, ("#F1F5F9", "#334155"))
        self._msg_label.setText(message)
        self._msg_label.setStyleSheet(
            f"color: {fg}; background-color: {bg}; font-size: 10pt; padding: 0 6px; border-radius: 4px;"
        )

        if transient:
            self._revert_timer.start(_TRANSIENT_DURATION_MS)

        logger.debug("[StatusBar] %s — %s", severity.value.upper(), message)

    def show_info(self, message: str) -> None:
        """Convenience: show an INFO-level transient message."""
        self.show_message(message, MessageSeverity.INFO)

    def show_success(self, message: str) -> None:
        """Convenience: show a SUCCESS-level transient message."""
        self.show_message(message, MessageSeverity.SUCCESS)

    def show_warning(self, message: str) -> None:
        """Convenience: show a WARNING-level transient message."""
        self.show_message(message, MessageSeverity.WARNING)

    def show_error(self, message: str) -> None:
        """Convenience: show an ERROR-level transient message (stays until next message)."""
        self.show_message(message, MessageSeverity.ERROR, transient=False)

    def set_idle_message(self, message: str) -> None:
        """Set the persistent background message shown when no transient message is active."""
        self._idle_message = message
        self._revert_to_idle()

    def set_model_badge(self, model_name: str) -> None:
        """Update the model-name pill badge on the right side of the bar."""
        display = model_name.replace("🤖 ", "").strip()
        self._badge_label.setText(f"  {display}  " if display else "")
        self._badge_widget.setVisible(bool(display))

    # ── Internal ────────────────────────────────────────────────────────────

    def _revert_to_idle(self) -> None:
        """Restore the idle message with neutral INFO styling."""
        self._revert_timer.stop()
        bg, fg = _SEVERITY_STYLES[MessageSeverity.INFO]
        self._msg_label.setText(self._idle_message)
        self._msg_label.setStyleSheet(
            f"color: {fg}; font-size: 10pt; padding: 0 6px;"
        )
