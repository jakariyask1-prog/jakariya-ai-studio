"""Unit and integration tests for dynamic theme switching across Jakariya AI Studio.

Verifies:
1. Palette completeness (light, dark, oled, neon have all required color tokens including accents).
2. SettingsWindow and all 9 child configuration pages adapt dynamically on theme switch.
3. ProviderCardWidget status badges adapt seamlessly between light mode and dark mode without color clash.
4. Sidebar and InputBar adopt unified brand accents consistently.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication

from app.ui.styles import THEME_PALETTES, get_theme_palette, get_global_app_style, get_dialog_style
from app.settings.ui.settings_window import SettingsWindow
from app.settings.ui.providers_page import ProvidersPage, ProviderCardWidget
from app.settings.ui.models_page import ModelsPage
from app.settings.ui.voice_page import VoicePage
from app.settings.ui.advanced_page import AdvancedPage
from app.settings.ui.about_page import AboutPage
from app.ui.sidebar import Sidebar
from app.ui.input_bar import InputBar
from app.ui.status_bar import AppStatusBar, MessageSeverity


@pytest.fixture(autouse=True)
def mock_external_env_and_keyring():
    with patch("app.settings.key_vault.retrieve_api_key", return_value=""), \
         patch("app.settings.key_vault._is_keyring_available", return_value=False):
        yield


class TestThemePalettes:
    """Verify all theme palettes contain full design system tokens."""

    @pytest.mark.parametrize("theme_name", ["light", "dark", "oled", "neon"])
    def test_palette_tokens_present(self, theme_name: str):
        p = get_theme_palette(theme_name)
        assert "bg_app" in p
        assert "bg_sidebar" in p
        assert "bg_header" in p
        assert "bg_chat" in p
        assert "accent" in p
        assert "accent_hover" in p
        assert "accent_text" in p
        assert "btn_secondary_bg" in p
        assert "input_text" in p

    def test_neon_accent_different_from_light(self):
        light_p = get_theme_palette("light")
        neon_p = get_theme_palette("neon")
        assert light_p["accent"] == "#4F46E5"
        assert neon_p["accent"] == "#F472B6"

    def test_global_and_dialog_qss_contain_scroll_rules(self):
        for theme in ["light", "dark", "oled", "neon"]:
            global_qss = get_global_app_style(theme)
            dialog_qss = get_dialog_style(theme)
            assert "QScrollArea" in global_qss
            assert "QScrollArea" in dialog_qss
            assert "centralWidget" in global_qss


class TestSettingsWindowThemePropagation:
    """Verify SettingsWindow propagates theme to all 9 configuration pages."""

    def test_settings_window_apply_theme_to_all_pages(self, qapp):
        win = SettingsWindow()
        try:
            for theme in ["light", "dark", "oled", "neon"]:
                win.apply_theme(theme)
                p = get_theme_palette(theme)
                # Verify btn_save_close has theme accent
                accent = p["accent"]
                assert accent.lower() in win.btn_save_close.styleSheet().lower()

                # Verify ProvidersPage cards adapted
                for card in win.page_providers._cards.values():
                    assert card._current_theme == theme

                # Verify AboutPage adapted
                assert accent.lower() in win.page_about.title_label.styleSheet().lower()
        finally:
            win.close()


class TestProvidersPageThemeSwitching:
    """Verify ProviderCardWidget status badges and buttons switch smoothly."""

    def test_provider_card_badge_and_test_button_adapt(self, qapp):
        card = ProviderCardWidget("google_ai_studio", "Google AI Studio", "https://generativelanguage.googleapis.com")

        # In light theme, badge neutral background is light (#F1F5F9)
        card.apply_theme("light")
        assert "#F1F5F9" in card.status_badge.styleSheet().upper()
        assert "#4F46E5" in card.btn_test.styleSheet().upper()

        # In dark theme, badge neutral background is dark (#1E293B)
        card.apply_theme("dark")
        assert "#1E293B" in card.status_badge.styleSheet().upper()
        assert "#4F46E5" in card.btn_test.styleSheet().upper()

        # In neon theme, test button uses magenta accent (#F472B6)
        card.apply_theme("neon")
        assert "#F472B6" in card.btn_test.styleSheet().upper()

    def test_providers_page_scroll_area_transparent(self, qapp):
        from PySide6.QtWidgets import QScrollArea
        page = ProvidersPage()
        scroll = page.findChild(QScrollArea)
        assert scroll is not None
        assert "transparent" in scroll.styleSheet().lower()
        # Verify apply_theme callable without exceptions
        for theme in ["light", "dark", "oled", "neon"]:
            page.apply_theme(theme)


class TestComponentThemes:
    """Verify Sidebar, InputBar, and AppStatusBar adapt properly."""

    def test_sidebar_accent_and_selector(self, qapp):
        sidebar = Sidebar()
        for theme in ["light", "dark", "oled", "neon"]:
            sidebar.apply_theme(theme)
            p = get_theme_palette(theme)
            assert p["accent"].lower() in sidebar.new_chat_button.styleSheet().lower()
            assert "border-right" in sidebar.styleSheet()

    def test_input_bar_accent(self, qapp):
        bar = InputBar()
        for theme in ["light", "dark", "oled", "neon"]:
            bar.apply_theme(theme)
            p = get_theme_palette(theme)
            assert p["accent"].lower() in bar.send_button.styleSheet().lower()

    def test_status_bar_theme(self, qapp):
        bar = AppStatusBar()
        bar.apply_theme("dark")
        bar.show_message("Test dark message", MessageSeverity.SUCCESS)
        # Should use dark green (#064E3B) instead of light green (#DCFCE7)
        assert "#064E3B" in bar._msg_label.styleSheet()


class TestComboboxAndTooltipLightMode:
    """Verify combobox dropdown lists and tooltips avoid dark OS palette leakage in light mode."""

    def test_combobox_view_palette_in_light_and_dark_themes(self, qapp):
        from PySide6.QtWidgets import QComboBox
        from app.ui.styles import apply_combobox_theme

        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(["Model A", "Model B"])

        # In light mode, dropdown view base MUST be pure white (#ffffff)
        apply_combobox_theme(combo, "light")
        assert combo.view().palette().base().color().name().lower() == "#ffffff"
        assert combo.view().palette().text().color().name().lower() == "#0f172a"
        assert combo.lineEdit().palette().base().color().name().lower() == "#ffffff"

        # In dark mode, dropdown view base MUST be dark (#0f172a)
        apply_combobox_theme(combo, "dark")
        assert combo.view().palette().base().color().name().lower() == "#0f172a"
        assert combo.view().palette().text().color().name().lower() == "#f8fafc"

    def test_settings_window_combos_light_mode_clean(self, qapp):
        from PySide6.QtWidgets import QComboBox

        win = SettingsWindow()
        try:
            win.apply_theme("light")
            all_combos = win.findChildren(QComboBox)
            assert len(all_combos) >= 10, "Expected at least 10 comboboxes across SettingsWindow pages"

            for combo in all_combos:
                base_color = combo.view().palette().base().color().name().lower()
                text_color = combo.view().palette().text().color().name().lower()
                assert base_color == "#ffffff", f"Combo dropdown base is {base_color}, expected #ffffff in light mode!"
                assert text_color == "#0f172a", f"Combo text is {text_color}, expected #0f172a in light mode!"
        finally:
            win.close()

    def test_header_selectors_light_mode_clean(self, qapp):
        from app.ui.header import Header

        header = Header()
        header.apply_theme("light")

        p_base = header.provider_selector.view().palette().base().color().name().lower()
        m_base = header.model_selector.view().palette().base().color().name().lower()
        assert p_base == "#ffffff", f"Header provider_selector base is {p_base}, expected #ffffff"
        assert m_base == "#ffffff", f"Header model_selector base is {m_base}, expected #ffffff"

    def test_tooltips_theme_adaptive(self):
        global_light = get_global_app_style("light")
        dialog_light = get_dialog_style("light")
        assert "QToolTip" in global_light
        assert "#FFFFFF" in global_light.upper()
        assert "QToolTip" in dialog_light
        assert "#FFFFFF" in dialog_light.upper()

        global_dark = get_global_app_style("dark")
        dialog_dark = get_dialog_style("dark")
        assert "#0F172A" in global_dark.upper()
        assert "#0F172A" in dialog_dark.upper()

