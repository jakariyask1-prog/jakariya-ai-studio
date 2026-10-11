"""Coverage for safe text extraction in the agent file reader."""

from pathlib import Path

from docx import Document

from app.agent.tools.base_tool import PermissionLevel
from app.agent.tools.file_tool import FileReadTool


def test_file_read_tool_extracts_docx_text(tmp_path: Path):
    document_path = tmp_path / "sample.docx"
    document = Document()
    document.add_paragraph("Document content")
    document.save(document_path)

    tool = FileReadTool()
    result = tool.execute(file_path=str(document_path))

    assert tool.permission_level == PermissionLevel.REQUIRES_APPROVAL
    assert result.success
    assert "Document content" in result.output


def test_file_read_tool_rejects_unsupported_file_type(tmp_path: Path):
    secret_path = tmp_path / "private.key"
    secret_path.write_text("private", encoding="utf-8")

    result = FileReadTool().execute(file_path=str(secret_path))

    assert not result.success
    assert "Unsupported file type" in result.error
