"""Unit tests for Settings Window Minimization System (Window & Sidebar Options)."""

import unittest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.settings.ui.settings_window import SettingsWindow
from app.ui.main_window import MainWindow

_APP = QApplication.instance() or QApplication([])


class TestSettingsWindowMinimization(unittest.TestCase):
    """Test suite verifying minimization functionality for SettingsWindow and MainWindow integration."""

    def test_settings_window_flags_and_buttons(self):
        win = SettingsWindow()

        # 1. Native Window Controls Flags
        flags = win.windowFlags()
        self.assertTrue(bool(flags & Qt.WindowType.WindowMinimizeButtonHint), "Minimize hint flag missing")
        self.assertTrue(bool(flags & Qt.WindowType.WindowMaximizeButtonHint), "Maximize hint flag missing")
        self.assertTrue(bool(flags & Qt.WindowType.WindowCloseButtonHint), "Close hint flag missing")

        # 2. In-window Minimize Button
        self.assertIsNotNone(win.btn_minimize)
        self.assertTrue(win.btn_minimize.isVisibleTo(win))
        self.assertIn("Minimize", win.btn_minimize.text())

        # 3. Sidebar toggle button and state
        self.assertIsNotNone(win.btn_toggle_sidebar)
        self.assertFalse(win.is_sidebar_minimized)
        self.assertEqual(win.sidebar.width(), 210)

        # Toggle to compact/minimized options sidebar
        win.toggle_sidebar_minimized()
        self.assertTrue(win.is_sidebar_minimized)
        self.assertEqual(win.sidebar.width(), 60)
        self.assertEqual(win.btn_toggle_sidebar.text(), "▶")
        self.assertEqual(win.sidebar.item(0).text(), "⚙️")

        # Toggle back to expanded options sidebar
        win.toggle_sidebar_minimized()
        self.assertFalse(win.is_sidebar_minimized)
        self.assertEqual(win.sidebar.width(), 210)
        self.assertEqual(win.btn_toggle_sidebar.text(), "◀ Minimize Options")
        self.assertIn("General", win.sidebar.item(0).text())

    def test_main_window_open_and_restore_settings_dialog(self):
        main_win = MainWindow()
        main_win.show()

        # Open settings window
        main_win.open_settings_window()
        self.assertIsNotNone(main_win._settings_dialog)
        self.assertTrue(main_win._settings_dialog.isVisible())

        # Simulate minimizing settings window
        main_win._settings_dialog.showMinimized()
        self.assertTrue(main_win._settings_dialog.isMinimized())

        # Calling open_settings_window again should un-minimize and focus
        main_win.open_settings_window()
        self.assertFalse(main_win._settings_dialog.isMinimized())

        # Closing settings dialog should reset reference
        main_win._settings_dialog.accept()
        self.assertIsNone(main_win._settings_dialog)

        main_win.close()


if __name__ == "__main__":
    unittest.main()
