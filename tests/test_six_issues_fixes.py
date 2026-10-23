"""Unit and Integration tests verifying fixes for the 6 reported issues:
1. Lock Agent and Live buttons during operations; prevent mode drift and cancellation hijack.
2. Bind Live Conversation strictly to its originating chat; prevent leaks into other chats.
3. Prevent ghost user message when Agent license/permission is not present.
4. Ensure checkable Live button resets to unchecked when Premium Live Voice is blocked.
5. Ensure Agent progress card, error badges, diff badges, and folder badges follow Dark/OLED/Neon themes.
6. Verify test-order independence with global ProviderManager cleanup after integration tests.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.ui.input_bar import InputBar
from app.ui.chat_area import ChatArea
from app.ui.header import Header
from app.ui.main_window import MainWindow
from app.providers.manager.provider_manager import ProviderManager
from tests.test_system_integration import TestSystemIntegration

_APP = QApplication.instance() or QApplication([])


class TestSixIssuesFixes(unittest.TestCase):
    """Test suite covering all 6 reported issues."""

    @classmethod
    def setUpClass(cls):
        from app.database import DatabaseService
        cls._db_service = DatabaseService()
        cls._db_service.initialize()

    def setUp(self):
        ProviderManager.reset_instance()

    def tearDown(self):
        ProviderManager.reset_instance()

    # -------------------------------------------------------------------------
    # Issue 1: High — Lock Agent and Live buttons during operations
    # -------------------------------------------------------------------------
    def test_issue_1_input_controls_locked_during_operations(self):
        """InputBar must disable Agent & Live buttons during standard chat, agent, or live session."""
        bar = InputBar()

        # Idle state: all buttons enabled
        self.assertTrue(bar.agent_button.isEnabled())
        self.assertTrue(bar.live_button.isEnabled())
        self.assertTrue(bar.voice_button.isEnabled())
        self.assertTrue(bar.attach_button.isEnabled())
        self.assertTrue(bar.folder_button.isEnabled())
        self.assertTrue(bar.message_input.isEnabled())
        self.assertTrue(bar.send_button.isEnabled())

        # 1. Chat operation running
        bar.set_operation_state("chat")
        self.assertFalse(bar.agent_button.isEnabled())
        self.assertFalse(bar.live_button.isEnabled())
        self.assertFalse(bar.voice_button.isEnabled())
        self.assertFalse(bar.attach_button.isEnabled())
        self.assertFalse(bar.folder_button.isEnabled())
        self.assertFalse(bar.message_input.isEnabled())
        self.assertTrue(bar.send_button.isEnabled())  # Stop button
        self.assertEqual(bar.send_button.text(), "⏹")

        # 2. Agent operation running
        bar.set_operation_state("agent")
        self.assertFalse(bar.agent_button.isEnabled())
        self.assertFalse(bar.live_button.isEnabled())
        self.assertFalse(bar.voice_button.isEnabled())
        self.assertFalse(bar.message_input.isEnabled())
        self.assertTrue(bar.send_button.isEnabled())
        self.assertEqual(bar.send_button.text(), "⏹")

        # 3. Live operation running
        bar.set_operation_state("live")
        self.assertFalse(bar.agent_button.isEnabled())
        self.assertTrue(bar.live_button.isEnabled())   # Stop Live control remains enabled
        self.assertFalse(bar.voice_button.isEnabled())
        self.assertFalse(bar.message_input.isEnabled())
        self.assertFalse(bar.send_button.isEnabled())

        # Reset to idle
        bar.set_operation_state(None)
        self.assertTrue(bar.agent_button.isEnabled())
        self.assertTrue(bar.live_button.isEnabled())
        self.assertTrue(bar.voice_button.isEnabled())
        self.assertTrue(bar.message_input.isEnabled())
        self.assertTrue(bar.send_button.isEnabled())
        self.assertEqual(bar.send_button.text(), "↑")

    # -------------------------------------------------------------------------
    # Issue 2: High — Live Conversation locked to originating chat
    # -------------------------------------------------------------------------
    def test_issue_2_live_session_locked_to_originating_chat(self):
        """Live session saves transcripts and responses strictly to the chat where it started."""
        win = MainWindow()
        try:
            chat_a = win.chat_manager.get_active_chat()
            # Create another chat
            chat_b = win.chat_manager.create_new_chat()
            win.chat_manager.select_chat(chat_a.id)

            # Use free TTS for test isolation
            win.voice_controller.settings.tts_provider_id = "edge_neural_tts"

            # Mock realistic live session lifecycle
            live_active = [False]
            def _fake_start():
                live_active[0] = True
            def _fake_stop():
                live_active[0] = False

            with patch.object(win.voice_controller, "start_live_session", side_effect=_fake_start), \
                 patch.object(win.voice_controller, "stop_live_session", side_effect=_fake_stop), \
                 patch.object(win.voice_controller, "is_live_session_active", side_effect=lambda: live_active[0]):
                win.on_live_button_clicked()
                self.assertEqual(win._active_operation, "live")
                self.assertEqual(win._live_conversation_id, chat_a.id)

                # Sidebar switching is blocked during live session
                win.switch_chat(chat_b.id)
                # Active chat must still be chat_a
                self.assertEqual(win.chat_manager.get_active_chat().id, chat_a.id)

                # If an STT transcript arrives, it goes to chat_a
                win.on_voice_transcript_ready("হ্যালো এআই")
                msgs_a = win.chat_manager.get_messages(chat_a.id)
                msgs_b = win.chat_manager.get_messages(chat_b.id)
                self.assertTrue(any(m.content == "হ্যালো এআই" for m in msgs_a))
                self.assertFalse(any(m.content == "হ্যালো এআই" for m in msgs_b))

                # When AI response arrives, it also goes to chat_a
                win.on_voice_response_ready("হ্যাঁ বলুন, কিভাবে সাহায্য করতে পারি?")
                msgs_a = win.chat_manager.get_messages(chat_a.id)
                msgs_b = win.chat_manager.get_messages(chat_b.id)
                self.assertTrue(any(m.content == "হ্যাঁ বলুন, কিভাবে সাহায্য করতে পারি?" for m in msgs_a))
                self.assertFalse(any(m.content == "হ্যাঁ বলুন, কিভাবে সাহায্য করতে পারি?" for m in msgs_b))

                # Stop live session
                win._stop_live_session()
                self.assertIsNone(win._active_operation)
                self.assertIsNone(win._live_conversation_id)
        finally:
            win.close()

    # -------------------------------------------------------------------------
    # Issue 3: High — Agent permission missing prevents ghost message
    # -------------------------------------------------------------------------
    def test_issue_3_no_ghost_message_when_agent_license_missing(self):
        """If user lacks agent license, prompt is not appended as a ghost turn and editor is restored."""
        with patch("app.licensing.license_manager.LicenseManager.is_feature_allowed", return_value=False), \
             patch.object(MainWindow, "open_upgrade_window") as mock_upgrade:
            win = MainWindow()
            try:
                active_chat = win.chat_manager.get_active_chat()
                initial_msg_count = len(win.chat_manager.get_messages(active_chat.id))

                # Enable Agent button and send
                win.input_bar.agent_button.setChecked(True)
                test_prompt = "Build a multi-agent system from scratch"
                win.input_bar.message_input.setText(test_prompt)

                win.send_message(test_prompt)

                # Upgrade dialog was opened
                mock_upgrade.assert_called_once()

                # NO message added to database
                final_msg_count = len(win.chat_manager.get_messages(active_chat.id))
                self.assertEqual(final_msg_count, initial_msg_count)

                # Input text restored
                self.assertEqual(win.input_bar.message_input.text(), test_prompt)

                # No pending message created
                self.assertIsNone(win._pending_message)
                self.assertIsNone(win._active_operation)
            finally:
                win.close()

    # -------------------------------------------------------------------------
    # Issue 4: Medium — Premium Live Voice block resets Live button state
    # -------------------------------------------------------------------------
    def test_issue_4_premium_live_voice_block_resets_live_button(self):
        """When premium voice is blocked, the checkable Live button must not stay checked."""
        from app.settings.settings_manager import SettingsManager
        with patch("app.licensing.license_manager.LicenseManager.is_feature_allowed", return_value=False), \
             patch.object(SettingsManager.instance().service, "get_api_key", return_value=""), \
             patch.object(MainWindow, "open_upgrade_window"):

            win = MainWindow()
            try:
                # Configure premium TTS
                win.voice_controller.settings.tts_provider_id = "cartesia_tts"

                # User clicks checkable live button (Qt toggles it checked)
                win.input_bar.live_button.setChecked(True)
                win.on_live_button_clicked()

                # Live button must be reset to unchecked (False)
                self.assertFalse(win.input_bar.live_button.isChecked())
                self.assertIn("Live", win.input_bar.live_button.text())
                self.assertNotIn("Stop", win.input_bar.live_button.text())
                self.assertIsNone(win._active_operation)
            finally:
                win.close()

    # -------------------------------------------------------------------------
    # Issue 5: Medium — Agent progress card, error badge, diff badge theming
    # -------------------------------------------------------------------------
    def test_issue_5_agent_progress_card_themed_properly(self):
        """In Dark/OLED/Neon theme, Agent bubble, error badge, and diff badges use dark colors."""
        chat_area = ChatArea()

        for theme in ("dark", "oled", "neon"):
            chat_area.set_theme(theme)

            # 1. Bubble start must use dark card background (#1E293B)
            chat_area.start_agent_bubble()
            html = chat_area.chat_box.toHtml().lower()
            self.assertIn('bgcolor="#1e293b"', html)

            # 2. Error badge must use dark styling (#450a0a / #fca5a5) and NOT light (#fee2e2)
            chat_area.update_agent_progress("Observation: Error running tool 'bash'")
            html_after_err = chat_area.chat_box.toHtml().lower()
            self.assertIn("#450a0a", html_after_err)
            self.assertNotIn("#fee2e2", html_after_err)

            # 3. Diff badges and folder badge must use dark theme colors
            chat_area.update_agent_progress(
                "Modified main.py (+12 / -4 lines) in 'app/ui'",
                tool_name="edit_file",
                is_tool=True,
            )
            html_after_tool = chat_area.chat_box.toHtml().lower()
            # Added badge: dark green (#064e3b), not light (#dcfce7)
            self.assertIn("#064e3b", html_after_tool)
            self.assertNotIn("#dcfce7", html_after_tool)
            # Removed badge: dark red (#450a0a), not light (#fee2e2)
            self.assertIn("#450a0a", html_after_tool)
            self.assertNotIn("#fee2e2", html_after_tool)

            # 4. End agent bubble
            chat_area.end_agent_bubble("Final Answer: Task complete.")
            final_html = chat_area.chat_box.toHtml().lower()
            # Persistent timeline must not contain light #fee2e2
            self.assertNotIn("#fee2e2", final_html)

    # -------------------------------------------------------------------------
    # Issue 6: Low — Test suite test-order independence
    # -------------------------------------------------------------------------
    def test_issue_6_test_order_independence(self):
        """Header model loading succeeds even immediately following an integration test."""
        # 1. Run the integration test suite that registers 4 mock providers
        integ_test = TestSystemIntegration()
        integ_test.setUp()
        integ_test.test_claude_client_provider_resolution()
        integ_test.test_claude_client_delegation_to_provider_manager()
        integ_test.tearDown()

        # 2. Verify ProviderManager singleton was cleaned up
        mgr = ProviderManager.instance()
        providers = mgr.list_providers()
        self.assertGreaterEqual(len(providers), 7, f"Expected >= 7 providers, got {len(providers)}: {providers}")

        # 3. Header successfully loads all default providers without failing
        header = Header()
        self.assertGreaterEqual(header.provider_selector.count(), 7)


if __name__ == "__main__":
    unittest.main()
