"""Security regression tests for agent-provider routing and file output boundaries."""

from pathlib import Path
from unittest.mock import MagicMock

from app.agent.agent_engine import AIAgentEngine
from app.agent.tools.file_tool import FileWriteTool
from app.providers.models.chat_response import ChatResponse


def test_agent_uses_the_selected_provider_id():
    agent = AIAgentEngine()
    provider_manager = MagicMock()
    provider_manager.chat.return_value = ChatResponse(
        content="Final Answer: done",
        model="mock-model",
        provider_id="selected-provider",
    )
    agent.provider_manager = provider_manager

    agent.execute_task("Summarize this", model="mock-model", provider_id="selected-provider")

    assert provider_manager.chat.call_args.kwargs["provider_id"] == "selected-provider"


def test_file_write_rejects_paths_outside_user_export_folders(tmp_path: Path):
    result = FileWriteTool().execute(
        file_path=str(tmp_path / "outside-agent-workspace.txt"),
        content="must not be written",
    )

    assert not result.success
    assert "limited to Desktop, Documents, or Downloads" in result.error
