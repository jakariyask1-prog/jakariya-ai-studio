import pytest
from app.utils.document_detector import DocumentDetector, DetectedDocument
from app.ui.chat_area import ChatArea


def test_document_detector_long_report():
    sample_report = """# Executive AI Business Report 2026

## 1. Introduction
This comprehensive report outlines the strategic AI deployment model for enterprise scaling.
Artificial intelligence models have evolved into autonomous agent architectures.

## 2. Market Analysis
| Model | Provider | Throughput |
|---|---|---|
| DeepSeek V3 | OpenRouter | High |
| Claude 3.5 Sonnet | Anthropic | Ultra |

## 3. Financial Forecast
The projected ROI across Q1-Q4 demonstrates a 300% operational efficiency gain across dev teams.
    """ + (" Additional analytical breakdown text." * 30)

    doc: DetectedDocument = DocumentDetector.detect(sample_report)
    assert doc.is_document is True
    assert doc.title == "Executive AI Business Report 2026"
    assert doc.document_type == "Business Report"
    assert doc.has_tables is True
    assert doc.word_count >= 120
    assert doc.estimated_pages >= 1


def test_document_detector_short_chat_message():
    short_msg = "Hello! How can I help you today with your code?"
    doc: DetectedDocument = DocumentDetector.detect(short_msg)
    assert doc.is_document is False


def test_document_detector_compact_structured_document():
    compact_document = """# Weekly Project Plan

## Goal
Ship the export update this week.

## Tasks
- Add the new setting.
- Verify PDF and DOCX downloads.
"""

    doc = DocumentDetector.detect(compact_document)

    assert doc.is_document is True
    assert doc.title == "Weekly Project Plan"


def test_document_detector_roadmap():
    roadmap_text = """# Product Launch Timeline

## Phase 1: Foundation
Build core ReAct agent loop and provider failover dispatcher.

## Phase 2: Timeline UI
Implement Claude Desktop-style smart document cards and execution progress timelines.
    """ + (" Detailed execution milestones and tasks." * 15)

    doc: DetectedDocument = DocumentDetector.detect(roadmap_text)
    assert doc.is_document is True
    assert doc.document_type == "Project Roadmap"


def test_smart_document_card_html_generation():
    doc = DetectedDocument(
        is_document=True,
        title="Annual Financial Summary",
        document_type="Business Report",
        preview_text="This is the executive summary preview of the financial document.",
        word_count=520,
        estimated_pages=3,
        has_tables=True,
        raw_content="Full content text here..."
    )

    card_html = ChatArea._build_smart_document_card_html(doc, message_id=42)
    assert "Annual Financial Summary" in card_html
    assert "Business Report" in card_html
    assert "~3 pages" in card_html
    assert "520 words" in card_html
    assert 'href="docpreview:42"' in card_html
    assert 'href="responseexport:42:pdf"' in card_html
    assert 'href="responseexport:42:docx"' in card_html
    assert 'href="responseexport:42:md"' in card_html
    assert 'href="messagecopy:42"' in card_html
