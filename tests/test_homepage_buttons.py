"""Test suite verifying all Home Page and Main Window UI/UX buttons, starter cards, and interactions."""

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from app.ui.chat_area import ChatArea
from app.ui.input_bar import InputBar
from app.ui.header import Header
from app.ui.sidebar import Sidebar


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestHomePageStarterCards:
    """Tests verifying the 4 Bento starter workflow cards on the home screen."""

    def test_starter_card_smart_documents(self, qapp):
        chat_area = ChatArea()
        chat_area.show_empty_state()

        received_prompts = []
        chat_area.prompt_selected.connect(received_prompts.append)

        # Simulate clicking the Smart Documents starter card
        url = QUrl("promptcard:Create%20a%20comprehensive%20business%20proposal%20document%20with%20executive%20summary%2C%20KPI%20data%20tables%2C%20and%20action%20roadmap")
        chat_area._on_anchor_clicked(url)

        assert len(received_prompts) == 1
        assert "Create a comprehensive business proposal document" in received_prompts[0]

    def test_starter_card_code_engine(self, qapp):
        chat_area = ChatArea()
        chat_area.show_empty_state()

        received_prompts = []
        chat_area.prompt_selected.connect(received_prompts.append)

        # Simulate clicking Code Engine & Analysis card
        url = QUrl("promptcard:Write%20a%20production-ready%20Python%20script%20with%20unit%20tests%20and%20error%20handling")
        chat_area._on_anchor_clicked(url)

        assert len(received_prompts) == 1
        assert "Write a production-ready Python script" in received_prompts[0]

    def test_starter_card_visual_art(self, qapp):
        chat_area = ChatArea()
        chat_area.show_empty_state()

        received_prompts = []
        chat_area.prompt_selected.connect(received_prompts.append)

        # Simulate clicking AI Visual Art & Creation card
        url = QUrl("promptcard:Generate%20an%20image%20of%20a%20futuristic%20minimalist%20floating%20workspace%20with%20soft%20ambient%20glow%20and%20hyper-detailed%20reflections")
        chat_area._on_anchor_clicked(url)

        assert len(received_prompts) == 1
        assert "Generate an image of a futuristic minimalist floating workspace" in received_prompts[0]

    def test_starter_card_deep_research(self, qapp):
        chat_area = ChatArea()
        chat_area.show_empty_state()

        received_prompts = []
        chat_area.prompt_selected.connect(received_prompts.append)

        # Simulate clicking Deep Research & Voice card
        url = QUrl("promptcard:Explain%20the%20core%20architecture%20of%20Transformer%20models%20and%20attention%20mechanisms%20in%20clear%20terms")
        chat_area._on_anchor_clicked(url)

        assert len(received_prompts) == 1
        assert "Explain the core architecture of Transformer models" in received_prompts[0]


class TestInputBarButtons:
    """Tests verifying all action buttons in the bottom floating input bar."""

    def test_send_button_emits_message(self, qapp):
        input_bar = InputBar()

        received_messages = []
        input_bar.send_requested.connect(received_messages.append)

        # Enter text into the message input and click send
        input_bar.message_input.setText("Hello, Jakariya AI Studio!")
        input_bar.send_button.click()

        assert len(received_messages) == 1
        assert received_messages[0] == "Hello, Jakariya AI Studio!"
        assert input_bar.message_input.toPlainText() == ""

    def test_attach_button_triggers_signal(self, qapp):
        input_bar = InputBar()

        received = []
        input_bar.attach_requested.connect(lambda: received.append(True))
        input_bar.attach_button.click()

        assert len(received) == 1

    def test_agent_mode_button_toggle(self, qapp):
        input_bar = InputBar()

        assert not input_bar.agent_button.isChecked()
        input_bar.agent_button.click()
        assert input_bar.agent_button.isChecked()
        input_bar.agent_button.click()
        assert not input_bar.agent_button.isChecked()

    def test_live_mode_button_triggers_signal(self, qapp):
        input_bar = InputBar()

        received = []
        input_bar.live_requested.connect(lambda: received.append(True))
        input_bar.live_button.click()

        assert len(received) == 1

    def test_voice_button_triggers_signal(self, qapp):
        input_bar = InputBar()

        received = []
        input_bar.voice_requested.connect(lambda: received.append(True))
        input_bar.voice_button.click()

        assert len(received) == 1


class TestHeaderButtons:
    """Tests verifying header controls (settings, export, dropdowns)."""

    def test_settings_button_triggers_signal(self, qapp):
        header = Header()

        received = []
        header.settings_requested.connect(lambda: received.append(True))
        header.settings_button.click()

        assert len(received) == 1

    def test_provider_and_model_selectors_populate(self, qapp):
        header = Header()

        assert header.provider_selector.count() > 0
        assert header.model_selector.count() > 0


class TestSidebarButtons:
    """Tests verifying sidebar actions (New Chat, Import, Select Mode)."""

    def test_new_chat_button_triggers_signal(self, qapp):
        sidebar = Sidebar()

        received = []
        sidebar.new_chat_requested.connect(lambda: received.append(True))
        sidebar.new_chat_button.click()

        assert len(received) == 1

    def test_import_button_triggers_signal(self, qapp):
        sidebar = Sidebar()

        received = []
        sidebar.import_requested.connect(lambda: received.append(True))
        sidebar.import_button.click()

        assert len(received) == 1

    def test_select_mode_button_toggles_checkboxes(self, qapp):
        sidebar = Sidebar()

        assert not sidebar._is_check_mode
        sidebar.select_mode_button.click()
        assert sidebar._is_check_mode
        sidebar.select_mode_button.click()
        assert not sidebar._is_check_mode
