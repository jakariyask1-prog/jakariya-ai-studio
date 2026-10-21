"""Main Settings Window container widget for Jakariya AI Studio Phase 8 Architecture."""

from __future__ import annotations

import copy
import logging
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.settings.settings_manager import SettingsManager
from app.settings.ui.about_page import AboutPage
from app.settings.ui.advanced_page import AdvancedPage
from app.settings.ui.appearance_page import AppearancePage
from app.settings.ui.chat_page import ChatPage
from app.settings.ui.export_page import ExportPage
from app.settings.ui.general_page import GeneralPage
from app.settings.ui.models_page import ModelsPage
from app.settings.ui.providers_page import ProvidersPage
from app.settings.ui.voice_page import VoicePage


class ToastLabel(QLabel):
    """Temporary floating toast notification label shown at the bottom of SettingsWindow."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(28)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_success(self, message: str, duration_ms: int = 3000) -> None:
        self.setText(f"✅  {message}")
        self.setStyleSheet(
            "background-color: #065F46; color: #D1FAE5; font-weight: 600; "
            "font-size: 11px; border-radius: 6px; padding: 2px 14px;"
        )
        self.show()
        self._timer.start(duration_ms)

    def show_error(self, message: str, duration_ms: int = 4000) -> None:
        self.setText(f"❌  {message}")
        self.setStyleSheet(
            "background-color: #7F1D1D; color: #FEE2E2; font-weight: 600; "
            "font-size: 11px; border-radius: 6px; padding: 2px 14px;"
        )
        self.show()
        self._timer.start(duration_ms)

    def show_info(self, message: str, duration_ms: int = 3000) -> None:
        self.setText(f"ℹ️  {message}")
        self.setStyleSheet(
            "background-color: #1E3A8A; color: #BFDBFE; font-weight: 600; "
            "font-size: 12px; border-radius: 8px; padding: 4px 16px;"
        )
        self.show()
        self._timer.start(duration_ms)


class SettingsWindow(QDialog):
    """Main Settings Dialog containing sidebar navigation and 9 configuration pages."""

    theme_preview_requested = Signal(str)
    settings_applied = Signal()   # emitted after successful Apply/Save so main app can react

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Jakariya AI Studio — Settings & Personalization")
        self.resize(880, 520)
        self.setMinimumSize(800, 480)

        # Enable native window minimization, maximization, and top-level controls
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        self._sidebar_minimized = False
        self._is_finished_emitted = False
        self._manager = SettingsManager.instance()

        # Snapshot of schema at open time — used to detect unsaved changes & enable Cancel rollback
        self._original_schema = copy.deepcopy(self._manager.service.schema)
        self._has_unsaved_changes = False

        self._init_ui()
        self.load_all_settings()

        # Apply saved appearance theme to dialog
        active_theme = self._manager.service.schema.appearance.theme
        self.apply_theme(active_theme)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 12)
        main_layout.setSpacing(8)

        # Central Horizontal Area (Sidebar + Pages)
        center_layout = QHBoxLayout()
        center_layout.setSpacing(14)

        # 1. Left Sidebar Navigation Container
        self.sidebar_container = QWidget()
        sidebar_vbox = QVBoxLayout(self.sidebar_container)
        sidebar_vbox.setContentsMargins(0, 0, 0, 0)
        sidebar_vbox.setSpacing(6)

        # Options sidebar minimize/expand toggle button
        self.btn_toggle_sidebar = QPushButton("◀ Minimize Options")
        self.btn_toggle_sidebar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_sidebar.setToolTip("Minimize options sidebar to compact icons (Ctrl+B)")
        self.btn_toggle_sidebar.clicked.connect(self.toggle_sidebar_minimized)
        sidebar_vbox.addWidget(self.btn_toggle_sidebar)

        # Left Sidebar Navigation List
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(210)
        self.sidebar_container.setFixedWidth(210)

        # Add 9 Category Items: (icon, name, full_text, key)
        self._categories_data = [
            ("⚙️", "General", "⚙️  General", "general"),
            ("🎨", "Appearance", "🎨  Appearance", "appearance"),
            ("🔌", "AI Providers", "🔌  AI Providers", "providers"),
            ("🤖", "AI Models", "🤖  AI Models", "models"),
            ("🎙️", "Voice & Audio", "🎙️  Voice & Audio", "voice"),
            ("💬", "Chat & Persona", "💬  Chat & Persona", "chat"),
            ("📄", "Export Preferences", "📄  Export Preferences", "export"),
            ("🛠️", "Advanced", "🛠️  Advanced", "advanced"),
            ("ℹ️", "About Studio", "ℹ️  About Studio", "about"),
        ]

        for _icon, _name, full_text, key in self._categories_data:
            item = QListWidgetItem(full_text)
            item.setData(Qt.UserRole, key)
            self.sidebar.addItem(item)

        self.sidebar.currentRowChanged.connect(self._on_page_changed)
        sidebar_vbox.addWidget(self.sidebar, stretch=1)
        center_layout.addWidget(self.sidebar_container)

        # 2. Right Stacked Widget Area
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("settingsStackedWidget")
        self.stacked_widget.setStyleSheet("QStackedWidget#settingsStackedWidget { background-color: transparent; border: none; }")

        # Instantiate Pages
        self.page_general = GeneralPage()
        self.page_appearance = AppearancePage()
        self.page_providers = ProvidersPage()
        self.page_models = ModelsPage()
        self.page_voice = VoicePage()
        self.page_chat = ChatPage()
        self.page_export = ExportPage()
        self.page_advanced = AdvancedPage()
        self.page_about = AboutPage()

        # Connect appearance preview signal to update both dialog and app live
        self.page_appearance.theme_preview_requested.connect(self._on_theme_preview)

        # Track changes across all pages
        self.page_general.setting_changed.connect(self._on_any_setting_changed)
        self.page_appearance.setting_changed.connect(self._on_any_setting_changed)
        self.page_providers.setting_changed.connect(self._on_any_setting_changed)
        self.page_models.setting_changed.connect(self._on_any_setting_changed)
        self.page_voice.setting_changed.connect(self._on_any_setting_changed)
        self.page_chat.setting_changed.connect(self._on_any_setting_changed)
        self.page_export.setting_changed.connect(self._on_any_setting_changed)
        self.page_advanced.setting_changed.connect(self._on_any_setting_changed)

        # Add to stack in index order
        self.stacked_widget.addWidget(self.page_general)      # 0
        self.stacked_widget.addWidget(self.page_appearance)   # 1
        self.stacked_widget.addWidget(self.page_providers)    # 2
        self.stacked_widget.addWidget(self.page_models)       # 3
        self.stacked_widget.addWidget(self.page_voice)        # 4
        self.stacked_widget.addWidget(self.page_chat)         # 5
        self.stacked_widget.addWidget(self.page_export)       # 6
        self.stacked_widget.addWidget(self.page_advanced)     # 7
        self.stacked_widget.addWidget(self.page_about)        # 8

        center_layout.addWidget(self.stacked_widget, stretch=1)
        main_layout.addLayout(center_layout)

        # 3. Toast notification bar (sits between pages and buttons)
        self.toast = ToastLabel(self)
        main_layout.addWidget(self.toast)

        # 4. Bottom Action Button Bar
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self.btn_reset = QPushButton("Reset Defaults")
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self._on_reset_defaults)
        action_layout.addWidget(self.btn_reset)

        action_layout.addStretch()

        self.btn_minimize = QPushButton("🗕 Minimize")
        self.btn_minimize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minimize.setToolTip("Minimize Settings Window to Taskbar (Ctrl+M)")
        self.btn_minimize.clicked.connect(self.showMinimized)
        action_layout.addWidget(self.btn_minimize)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self._on_cancel)
        action_layout.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #FFFFFF;
                font-weight: bold;
                padding: 7px 18px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_apply.clicked.connect(self._on_apply)
        action_layout.addWidget(self.btn_apply)

        self.btn_save_close = QPushButton("Save & Close")
        self.btn_save_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_close.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: #FFFFFF;
                font-weight: bold;
                padding: 7px 20px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        self.btn_save_close.clicked.connect(self._on_save_and_close)
        action_layout.addWidget(self.btn_save_close)

        main_layout.addLayout(action_layout)

        # Keyboard shortcuts for quick minimizing
        self._shortcut_sidebar = QShortcut(QKeySequence("Ctrl+B"), self)
        self._shortcut_sidebar.activated.connect(self.toggle_sidebar_minimized)

        self._shortcut_minimize_win = QShortcut(QKeySequence("Ctrl+M"), self)
        self._shortcut_minimize_win.activated.connect(self.showMinimized)

        # Set default active page to General (0)
        self.sidebar.setCurrentRow(0)

    # ------------------------------------------------------------------
    # Unsaved-change tracking
    # ------------------------------------------------------------------

    def _on_any_setting_changed(self, *_args) -> None:
        """Mark that there are unsaved changes in any page."""
        self._has_unsaved_changes = True

    # ------------------------------------------------------------------
    # Theme handling
    # ------------------------------------------------------------------

    def _on_theme_preview(self, theme_name: str) -> None:
        self.apply_theme(theme_name)
        self.theme_preview_requested.emit(theme_name)

    def apply_theme(self, theme_name: str) -> None:
        """Apply active theme styles to SettingsWindow container and child controls."""
        from app.ui.styles import get_theme_palette, get_dialog_style
        p = get_theme_palette(theme_name)
        accent = "#4F46E5" if theme_name in ("light", "dark", "oled") else "#F472B6"

        # Apply comprehensive dialog stylesheet across all pages and child widgets
        self.setStyleSheet(get_dialog_style(theme_name))

        self.sidebar.setStyleSheet(f"""
            QListWidget {{
                font-size: 10.5pt;
                font-weight: 500;
                border: 1px solid {p['border_sidebar']};
                border-radius: 12px;
                background-color: {p['bg_sidebar']};
                outline: none;
                padding: 6px;
            }}
            QListWidget::item {{
                padding: 10px 14px;
                border-radius: 8px;
                margin: 3px 0px;
                color: {p['btn_secondary_text']};
            }}
            QListWidget::item:hover {{
                background-color: {p['item_hover']};
                color: {p['input_text']};
            }}
            QListWidget::item:selected {{
                background-color: {p['item_selected']};
                color: {p['item_selected_text']};
                font-weight: 700;
                border-left: 3px solid {accent};
            }}
        """)

        btn_sec_qss = f"""
            QPushButton {{
                background-color: {p['btn_secondary_bg']};
                color: {p['btn_secondary_text']};
                border: 1px solid {p['btn_secondary_border']};
                padding: 7px 16px;
                border-radius: 8px;
                font-size: 9.5pt;
                font-weight: 600;
            }}
            QPushButton:hover {{ 
                background-color: {p['btn_secondary_hover']}; 
                color: {p['input_text']}; 
                border-color: {accent};
            }}
        """
        self.btn_reset.setStyleSheet(btn_sec_qss)
        self.btn_cancel.setStyleSheet(btn_sec_qss)
        self.btn_minimize.setStyleSheet(btn_sec_qss)
        self.btn_apply.setStyleSheet(btn_sec_qss)

        toggle_btn_qss = f"""
            QPushButton {{
                background-color: {p['btn_secondary_bg']};
                color: {p['btn_secondary_text']};
                border: 1px solid {p['btn_secondary_border']};
                padding: 6px 10px;
                border-radius: 8px;
                font-size: 9pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {p['btn_secondary_hover']};
                color: {p['input_text']};
                border-color: {accent};
            }}
        """
        self.btn_toggle_sidebar.setStyleSheet(toggle_btn_qss)

        # Update Primary Save & Close button dynamically with active theme accent
        accent_hover = p.get("accent_hover", "#4338CA")
        self.btn_save_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: #FFFFFF;
                font-weight: bold;
                padding: 7px 20px;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{ background-color: {accent_hover}; }}
        """)

        # Propagate active theme to all stacked child pages
        for i in range(self.stacked_widget.count()):
            page = self.stacked_widget.widget(i)
            if hasattr(page, "apply_theme") and callable(page.apply_theme):
                try:
                    page.apply_theme(theme_name)
                except Exception as err:
                    logging.debug(f"[SettingsWindow] Failed to apply theme to page {i}: {err}")

        # Ensure all QComboBox controls across all dialog pages have their popup views and palettes synchronized
        try:
            from app.ui.styles import apply_combobox_theme
            for combo in self.findChildren(QComboBox):
                apply_combobox_theme(combo, theme_name)
        except Exception as err:
            logging.debug(f"[SettingsWindow] Failed to synchronize combo themes: {err}")

        # Apply Windows 11 native Mica / Acrylic backdrop and dark titlebar to Settings Dialog
        try:
            from app.ui.dwm_blur import apply_dwm_backdrop
            is_dark = str(theme_name).lower() in ("dark", "oled", "neon")
            apply_dwm_backdrop(int(self.winId()), is_dark=is_dark, backdrop_type="acrylic")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Page navigation
    # ------------------------------------------------------------------

    def _on_page_changed(self, row: int) -> None:
        if 0 <= row < self.stacked_widget.count():
            self.stacked_widget.setCurrentIndex(row)

    # ------------------------------------------------------------------
    # Sidebar Minimization Controls
    # ------------------------------------------------------------------

    @property
    def is_sidebar_minimized(self) -> bool:
        """Check whether the options sidebar is currently minimized."""
        return self._sidebar_minimized

    def toggle_sidebar_minimized(self) -> None:
        """Toggle options sidebar between full-width (210px) and minimized (60px compact icons)."""
        self.set_sidebar_minimized(not self._sidebar_minimized)

    def set_sidebar_minimized(self, minimized: bool) -> None:
        """Set whether options sidebar is minimized."""
        self._sidebar_minimized = bool(minimized)
        current_row = self.sidebar.currentRow()
        if self._sidebar_minimized:
            self.sidebar.setFixedWidth(60)
            self.sidebar_container.setFixedWidth(60)
            self.btn_toggle_sidebar.setText("▶")
            self.btn_toggle_sidebar.setToolTip("Expand options sidebar (Ctrl+B)")
            for i, (icon, name, _full, _key) in enumerate(self._categories_data):
                item = self.sidebar.item(i)
                if item:
                    item.setText(icon)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setToolTip(f"{name} Settings")
        else:
            self.sidebar.setFixedWidth(210)
            self.sidebar_container.setFixedWidth(210)
            self.btn_toggle_sidebar.setText("◀ Minimize Options")
            self.btn_toggle_sidebar.setToolTip("Minimize options sidebar (Ctrl+B)")
            for i, (_icon, _name, full_text, _key) in enumerate(self._categories_data):
                item = self.sidebar.item(i)
                if item:
                    item.setText(full_text)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    item.setToolTip("")
        if current_row >= 0:
            self.sidebar.setCurrentRow(current_row)

    # ------------------------------------------------------------------
    # Load / Apply
    # ------------------------------------------------------------------

    def load_all_settings(self) -> None:
        """Load current settings from ConfigurationService into all UI pages."""
        schema = self._manager.service.schema
        self.page_general.load_settings(schema.general)
        self.page_appearance.load_settings(schema.appearance)
        self.page_providers.load_settings(schema.providers)
        self.page_models.load_settings(schema.models)
        self.page_voice.load_settings(schema.voice)
        self.page_chat.load_settings(schema.chat)
        self.page_export.load_settings(schema.export)
        self.page_advanced.load_settings(schema.advanced)
        self.page_about.load_settings(schema.about)
        self._has_unsaved_changes = False

    def apply_all_settings(self) -> bool:
        """Collect settings from all UI pages, save to ConfigurationService and disk."""
        # Validate Base URLs first
        url_errors = self.page_providers.validate()
        if url_errors:
            self.toast.show_error("Invalid URL(s): " + "; ".join(url_errors[:2]))
            return False

        try:
            gen = self.page_general.get_settings()
            app = self.page_appearance.get_settings()
            provs = self.page_providers.get_settings()
            mods = self.page_models.get_settings()
            v_conf = self.page_voice.get_settings()
            c_conf = self.page_chat.get_settings()
            e_conf = self.page_export.get_settings()
            a_conf = self.page_advanced.get_settings()
            about_conf = self.page_about.get_settings()

            svc = self._manager.service

            # --- Persist API keys to keyring before committing ---
            from app.settings.key_vault import store_api_key, _is_keyring_available
            from app.settings.settings_schema import ProviderConfig
            scrubbed_provs: dict[str, ProviderConfig] = {}
            for p_id, p_conf in provs.items():
                if p_conf.api_key and p_conf.api_key not in ("", "__keyring__"):
                    if _is_keyring_available() and store_api_key(p_id, p_conf.api_key):
                        p_conf = ProviderConfig(
                            name=p_conf.name,
                            enabled=p_conf.enabled,
                            api_key="__keyring__",
                            base_url=p_conf.base_url,
                            status=p_conf.status,
                            priority=p_conf.priority,
                        )
                scrubbed_provs[p_id] = p_conf

            svc.schema.general = gen
            svc.schema.appearance = app
            svc.schema.providers = scrubbed_provs
            svc.schema.models = mods
            svc.schema.voice = v_conf
            svc.schema.chat = c_conf
            svc.schema.export = e_conf
            svc.schema.advanced = a_conf
            svc.schema.about = about_conf

            success = svc.save()
            if success:
                # Update snapshot so Cancel no longer prompts
                self._original_schema = copy.deepcopy(svc.schema)
                self._has_unsaved_changes = False
                # Apply runtime settings to the running application
                self._apply_runtime_settings(gen, app, a_conf)
                self.settings_applied.emit()
                logging.info("[SettingsWindow] All settings applied successfully.")
            return success
        except Exception as exc:
            logging.exception(f"[SettingsWindow] Failed to apply settings: {exc}")
            return False

    def _apply_runtime_settings(self, gen, app, adv) -> None:
        """Apply settings that must take effect immediately at runtime without restart."""
        import logging as _logging

        # 1. Log level
        try:
            level = getattr(_logging, adv.log_level.upper(), _logging.INFO)
            _logging.getLogger().setLevel(level)
        except Exception:
            pass

        # 2. Auto-startup (Windows registry)
        try:
            self._apply_auto_startup(gen.auto_startup)
        except Exception:
            pass

        # 3. Font scale — emit signal so main app can pick it up
        # (main_window listens to settings_applied and re-applies theme/font)

    @staticmethod
    def _apply_auto_startup(enable: bool) -> None:
        """Register or remove Jakariya AI Studio from Windows startup registry."""
        import sys, winreg  # noqa: E401
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "JakariyaAIStudio"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                winreg.KEY_SET_VALUE) as reg_key:
                if enable:
                    exe_path = sys.executable
                    winreg.SetValueEx(reg_key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
                else:
                    try:
                        winreg.DeleteValue(reg_key, app_name)
                    except FileNotFoundError:
                        pass  # Already removed — fine
        except Exception as exc:
            logging.debug("[SettingsWindow] Auto-startup registry update skipped: %s", exc)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_apply(self) -> None:
        """Apply settings and show success/error toast."""
        success = self.apply_all_settings()
        if success:
            self.toast.show_success("Settings applied successfully.")
        else:
            self.toast.show_error("Failed to save settings. Check logs for details.")

    def _on_save_and_close(self) -> None:
        self.page_providers.stop_all_tests()
        success = self.apply_all_settings()
        if success:
            self.accept()
        else:
            self.toast.show_error("Failed to save settings. Changes not committed.")

    def _on_reset_defaults(self) -> None:
        """Ask for confirmation before resetting; do NOT save until user clicks Apply/Save."""
        reply = QMessageBox.question(
            self,
            "Reset to Defaults",
            "Are you sure you want to reset ALL settings to factory defaults?\n\n"
            "Click 'Apply' or 'Save & Close' to confirm the reset, or 'Cancel' to discard.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Reset in-memory only — NOT saved to disk yet
        self._manager.service.reset_defaults()
        self.load_all_settings()
        self._has_unsaved_changes = True
        self.toast.show_info("Defaults loaded. Click 'Apply' to save, or 'Cancel' to discard.")

    def _on_cancel(self) -> None:
        """Cancel: warn if there are unsaved changes, then rollback in-memory schema."""
        self.page_providers.stop_all_tests()
        if self._has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Discard them and close?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Discard:
                return

        # Rollback: restore original schema in memory (no disk write needed, nothing changed on disk)
        self._manager.service.schema = self._original_schema
        # Revert live theme preview to saved theme
        saved_theme = self._original_schema.appearance.theme
        self.theme_preview_requested.emit(saved_theme)
        self.reject()

    def accept(self) -> None:
        self._is_finished_emitted = True
        super().accept()

    def reject(self) -> None:
        self._is_finished_emitted = True
        super().reject()

    def closeEvent(self, event) -> None:
        """Intercept window X-button close to check for unsaved changes."""
        self.page_providers.stop_all_tests()
        if self._has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Discard them and close?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Discard:
                event.ignore()
                return
            # Rollback
            self._manager.service.schema = self._original_schema
            saved_theme = self._original_schema.appearance.theme
            self.theme_preview_requested.emit(saved_theme)
        if not getattr(self, "_is_finished_emitted", False):
            self._is_finished_emitted = True
            self.setResult(self.DialogCode.Rejected)
            self.finished.emit(self.DialogCode.Rejected)
        event.accept()

