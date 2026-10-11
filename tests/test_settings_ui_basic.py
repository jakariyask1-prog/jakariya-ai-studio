"""Unit tests for Phase 8 Settings UI Basic Pages (Milestone 2)."""

import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from app.settings.settings_schema import GeneralSettings, AppearanceSettings, AboutSettingsSchema
from app.settings.ui.general_page import GeneralPage
from app.settings.ui.appearance_page import AppearancePage
from app.settings.ui.about_page import AboutPage
from app.settings.ui.settings_window import SettingsWindow

_APP = QApplication.instance() or QApplication([])


class TestSettingsUIBasic(unittest.TestCase):
    """Test suite for Settings Window, sidebar navigation, and basic UI pages."""

    def test_general_page_load_and_get(self):
        page = GeneralPage()
        g_in = GeneralSettings(language="bn", auto_startup=True, notifications_enabled=False)
        page.load_settings(g_in)

        g_out = page.get_settings()
        self.assertEqual(g_out.language, "bn")
        self.assertTrue(g_out.auto_startup)
        self.assertFalse(g_out.notifications_enabled)

    def test_appearance_page_load_and_get(self):
        page = AppearancePage()
        a_in = AppearanceSettings(theme="oled", font_family="Consolas", font_scale=1.2, message_density="compact")
        page.load_settings(a_in)

        a_out = page.get_settings()
        self.assertEqual(a_out.theme, "oled")
        self.assertEqual(a_out.font_family, "Consolas")
        self.assertAlmostEqual(a_out.font_scale, 1.2, places=2)
        self.assertEqual(a_out.message_density, "compact")

    def test_about_page_load(self):
        page = AboutPage()
        ab_in = AboutSettingsSchema(app_name="Jakariya AI Studio Test", version="2.5.0", creator="Md. Jakariya Sheikh")
        page.load_settings(ab_in)
        self.assertEqual(page.title_label.text(), "Jakariya AI Studio Test")
        self.assertEqual(page.version_label.text(), "2.5.0")

    def test_settings_window_initialization(self):
        win = SettingsWindow()
        self.assertEqual(win.sidebar.count(), 9)
        self.assertEqual(win.stacked_widget.count(), 9)

        # Test page navigation
        win.sidebar.setCurrentRow(1)
        self.assertEqual(win.stacked_widget.currentIndex(), 1)

        win.sidebar.setCurrentRow(8)
        self.assertEqual(win.stacked_widget.currentIndex(), 8)

        # Test save and apply
        self.assertTrue(win.apply_all_settings())

    def test_settings_window_minimization_and_sidebar_toggle(self):
        from PySide6.QtCore import Qt
        win = SettingsWindow()

        # 1. Verify window minimization flags
        flags = win.windowFlags()
        self.assertTrue(bool(flags & Qt.WindowType.WindowMinimizeButtonHint))
        self.assertTrue(bool(flags & Qt.WindowType.WindowMaximizeButtonHint))

        # 2. Verify in-dialog minimize button
        self.assertIsNotNone(win.btn_minimize)
        self.assertIn("Minimize", win.btn_minimize.text())

        # 3. Verify options sidebar minimization toggle button
        self.assertIsNotNone(win.btn_toggle_sidebar)
        self.assertFalse(win.is_sidebar_minimized)
        self.assertEqual(win.sidebar.width(), 210)
        self.assertIn("General", win.sidebar.item(0).text())

        # Toggle to minimized state
        win.toggle_sidebar_minimized()
        self.assertTrue(win.is_sidebar_minimized)
        self.assertEqual(win.sidebar.width(), 60)
        self.assertEqual(win.btn_toggle_sidebar.text(), "▶")
        self.assertEqual(win.sidebar.item(0).text(), "⚙️")
        self.assertEqual(win.sidebar.item(0).toolTip(), "General Settings")

        # Toggle back to expanded state
        win.toggle_sidebar_minimized()
        self.assertFalse(win.is_sidebar_minimized)
        self.assertEqual(win.sidebar.width(), 210)
        self.assertIn("General", win.sidebar.item(0).text())
        self.assertEqual(win.sidebar.item(0).toolTip(), "")


if __name__ == "__main__":
    unittest.main()
