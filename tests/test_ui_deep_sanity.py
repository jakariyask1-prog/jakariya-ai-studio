"""Comprehensive UI & Settings deep sanity check."""

import os
import pytest
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.settings.ui.settings_window import SettingsWindow


def test_ui_and_settings_deep_sanity(qtbot):
    """Test full MainWindow and SettingsWindow lifecycle, pages, and theme switching."""
    win = MainWindow()
    qtbot.addWidget(win)

    sw = SettingsWindow(parent=win)
    qtbot.addWidget(sw)

    # Verify all 9 settings pages can be navigated without exceptions
    assert sw.sidebar.count() == 9
    for i in range(sw.sidebar.count()):
        sw.sidebar.setCurrentRow(i)
        assert sw.stacked_widget.currentIndex() == i

    # Verify dynamic theme switching across all 4 supported themes
    for theme in ["light", "dark", "oled", "neon"]:
        win.apply_theme(theme)
        sw.apply_theme(theme)

    # Verify settings window save/load
    sw.load_all_settings()

    # Clean close
    sw.close()
    win.close()


def test_voice_mode_transcribes_into_input_bar(qtbot):
    """Verify that in standard Voice Mode, speaking transcribes directly into the input bar."""
    win = MainWindow()
    qtbot.addWidget(win)

    # 1. Verify standard Voice Mode is active (not live conversation)
    assert not win.voice_controller.is_live_session_active()
    win.input_bar.clear()
    assert win.input_bar.message_input.text().strip() == ""

    # 2. Simulate speech recognition result coming from STT
    win.on_voice_transcript_ready("কেমন আছেন?")
    assert win.input_bar.message_input.text() == "কেমন আছেন?"

    # 3. Simulate another spoken clause; it should append cleanly with space
    win.on_voice_transcript_ready("আমি ভালো আছি।")
    assert win.input_bar.message_input.text() == "কেমন আছেন? আমি ভালো আছি।"

    win.close()


def test_live_mode_sends_to_chat_directly(qtbot):
    """Verify that in Live Voice Mode, speech is sent directly to the chat stream."""
    win = MainWindow()
    qtbot.addWidget(win)

    # Simulate Live Mode activated on manager
    win.voice_controller._manager._live_session_active = True
    assert win.voice_controller.is_live_session_active()

    # In Live Mode, transcript goes straight to chat conversation and leaves input bar clear
    win.on_voice_transcript_ready("লাইভ মোডে কথা বলছি")
    assert win.input_bar.message_input.text() == ""

    active_chat = win.chat_manager.get_active_chat()
    messages = win.chat_manager.get_messages(active_chat.id)
    assert any("লাইভ মোডে কথা বলছি" in m.content for m in messages)

    win.close()
