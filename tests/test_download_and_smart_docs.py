import pytest
from pathlib import Path
from app.utils.document_detector import DocumentDetector, DetectedDocument
from app.ui.chat_area import ChatArea
from app.export.export_manager import ExportManager
from app.export.export_service import ExportService
from app.export.business_logic import build_default_exporter_registry
from app.export.export_options import ExportOptions
from app.chat.chat_manager import ChatManager
from app.chat.chat_repository import ChatRepository
from app.database.database import DatabaseManager
from app.database.migrations import run_migrations


def test_smart_document_card_generation():
    doc = DocumentDetector.detect("""# AI Studio Strategic Roadmap 2026

## Phase 1: ReAct Engine
Integrate multi-turn planning, tool registry, and permission checks.

## Phase 2: Claude Desktop Cards
Add smart document cards, word count, estimated page count, and export buttons.
    """ + (" Detailed roadmap notes for project scaling." * 15))

    assert doc.is_document is True
    assert doc.title == "AI Studio Strategic Roadmap 2026"
    assert doc.document_type == "Project Roadmap"

    card_html = ChatArea._build_smart_document_card_html(doc, message_id=101)
    
    # Check for all action and download links
    assert 'href="docpreview:101"' in card_html
    assert 'href="responseexport:101:pdf"' in card_html
    assert 'href="responseexport:101:docx"' in card_html
    assert 'href="responseexport:101:md"' in card_html
    assert 'href="responseexport:101:txt"' in card_html
    assert 'href="messagecopy:101"' in card_html


def test_export_options_working(tmp_path):
    exporter_registry = build_default_exporter_registry()
    database = DatabaseManager(tmp_path / "test.db")
    run_migrations(database)
    chat_manager = ChatManager(ChatRepository(database))
    chat_manager.initialize()
    
    export_service = ExportService(chat_manager, exporter_registry)
    export_manager = ExportManager(export_service)
    
    sample_content = "# Sample Report\nThis is a test AI document for export verification."
    
    # Test PDF export
    pdf_dest = tmp_path / "test_report.pdf"
    res_pdf = export_manager.export_response(str(pdf_dest), ExportOptions("pdf"), "Sample Report", sample_content)
    assert pdf_dest.exists()
    assert res_pdf.destination.suffix.lower() == ".pdf"
    
    # Test DOCX export
    docx_dest = tmp_path / "test_report.docx"
    res_docx = export_manager.export_response(str(docx_dest), ExportOptions("docx"), "Sample Report", sample_content)
    assert docx_dest.exists()
    assert res_docx.destination.suffix.lower() == ".docx"

    # Test Markdown export
    md_dest = tmp_path / "test_report.md"
    res_md = export_manager.export_response(str(md_dest), ExportOptions("md"), "Sample Report", sample_content)
    assert md_dest.exists()
    assert md_dest.read_text(encoding="utf-8").strip() == sample_content

    # Test TXT export
    txt_dest = tmp_path / "test_report.txt"
    res_txt = export_manager.export_response(str(txt_dest), ExportOptions("txt"), "Sample Report", sample_content)
    assert txt_dest.exists()
    assert "Sample Report" in txt_dest.read_text(encoding="utf-8")
