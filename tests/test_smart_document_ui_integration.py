"""
UI-Level Integration Tests for Smart Document UI, Export Actions, and Preview Dialog.
Uses pytest-qt (qtbot) and verifies WCAG 2.1 AA/AAA color contrast compliance for Light and Dark Modes.
"""

import os
import pytest
from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.chat_area import ChatArea
from app.ui.document_preview_dialog import DocumentPreviewDialog
from app.utils.color_contrast import (
    contrast_ratio,
    is_wcag_aa_compliant,
    is_wcag_aaa_compliant,
)
from app.ui.styles import (
    SMART_DOC_LIGHT_CARD_BG,
    SMART_DOC_LIGHT_TITLE,
    SMART_DOC_LIGHT_BADGE_BG,
    SMART_DOC_LIGHT_BADGE_TEXT,
    SMART_DOC_LIGHT_PREVIEW_BG,
    SMART_DOC_LIGHT_PREVIEW_TEXT,
    SMART_DOC_LIGHT_LINK,
    SMART_DOC_DARK_CARD_BG,
    SMART_DOC_DARK_TITLE,
    SMART_DOC_DARK_BADGE_BG,
    SMART_DOC_DARK_BADGE_TEXT,
    SMART_DOC_DARK_PREVIEW_BG,
    SMART_DOC_DARK_PREVIEW_TEXT,
    SMART_DOC_DARK_LINK,
    SMART_DOC_DARK_MUTED,
)

SAMPLE_DOCUMENT_MARKDOWN = """# Executive AI Business Strategy 2026

## 1. Executive Summary
This enterprise report details the multi-turn agentic architecture for enterprise deployments.
Our AI Studio model incorporates ReAct loops, tool verification, and automatic failover handlers.

## 2. Key Performance Metrics
| Metric | Q1 Target | Q4 Forecast |
|---|---|---|
| Latency | < 500ms | < 250ms |
| Accuracy | 94% | 99.2% |
""" + (" Extended detailed strategic planning breakdown text." * 20)


def test_smart_document_card_rendering_in_chat_area(qtbot):
    """UI Integration Test: Verify Smart Document Card renders inside ChatArea widget."""
    chat_area = ChatArea()
    qtbot.addWidget(chat_area)

    msg_id = chat_area.append_assistant_message(SAMPLE_DOCUMENT_MARKDOWN)
    assert msg_id == 0

    html = chat_area.chat_box.toHtml()

    # Verify Smart Card elements in rendered HTML
    assert "Executive AI Business Strategy 2026" in html
    assert "Business Report" in html
    assert "words" in html
    assert 'href="docpreview:0"' in html
    assert 'href="responseexport:0:pdf"' in html
    assert 'href="responseexport:0:docx"' in html
    assert 'href="responseexport:0:xlsx"' in html
    assert 'href="responseexport:0:md"' in html
    assert 'href="responseexport:0:txt"' in html


def test_smart_document_export_signals_on_anchor_click(qtbot):
    """UI Integration Test: Verify clicking card export links emits response_export_requested signal."""
    chat_area = ChatArea()
    qtbot.addWidget(chat_area)

    msg_id = chat_area.append_assistant_message(SAMPLE_DOCUMENT_MARKDOWN)

    emitted_exports = []
    chat_area.response_export_requested.connect(
        lambda fmt, content: emitted_exports.append((fmt, content))
    )

    # Click PDF Export Link
    chat_area._on_anchor_clicked(QUrl(f"responseexport:{msg_id}:pdf"))
    assert len(emitted_exports) == 1
    assert emitted_exports[0][0] == "pdf"
    assert "Executive AI Business Strategy 2026" in emitted_exports[0][1]

    # Click DOCX Export Link
    chat_area._on_anchor_clicked(QUrl(f"responseexport:{msg_id}:docx"))
    assert len(emitted_exports) == 2
    assert emitted_exports[1][0] == "docx"

    # Click TXT Export Link
    chat_area._on_anchor_clicked(QUrl(f"responseexport:{msg_id}:txt"))
    assert len(emitted_exports) == 3
    assert emitted_exports[2][0] == "txt"


def test_smart_document_preview_dialog_ui_and_actions(qtbot, monkeypatch):
    """UI Integration Test: Verify DocumentPreviewDialog widget UI elements and clipboard copy action."""
    # Monkeypatch QMessageBox to prevent modal dialog hang in offscreen mode
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    dialog = DocumentPreviewDialog(
        title="Executive AI Strategy",
        document_type="Business Report",
        word_count=450,
        estimated_pages=2,
        raw_content=SAMPLE_DOCUMENT_MARKDOWN,
        theme="light",
    )
    qtbot.addWidget(dialog)

    assert "Document Preview — Executive AI Strategy" in dialog.windowTitle()
    assert dialog.text_browser is not None

    rendered_html = dialog.text_browser.toHtml()
    assert "Executive AI Business Strategy 2026" in rendered_html
    assert "Executive Summary" in rendered_html

    # Test clipboard copy action
    dialog._copy_to_clipboard()
    copied_text = QApplication.clipboard().text()
    assert copied_text == SAMPLE_DOCUMENT_MARKDOWN


def test_smart_document_dark_mode_ui_integration(qtbot):
    """UI Integration Test: Verify Smart Document Card & DocumentPreviewDialog render cleanly in Dark Mode."""
    chat_area = ChatArea()
    chat_area.set_theme("dark")
    qtbot.addWidget(chat_area)

    msg_id = chat_area.append_assistant_message(SAMPLE_DOCUMENT_MARKDOWN)
    html = chat_area.chat_box.toHtml()

    # Dark Mode card background and title colors present in card HTML
    assert SMART_DOC_DARK_CARD_BG.lower() in html.lower()
    assert SMART_DOC_DARK_TITLE.lower() in html.lower()

    # Document Preview Dialog Dark Mode test
    dark_dialog = DocumentPreviewDialog(
        title="Executive AI Strategy",
        document_type="Business Report",
        word_count=450,
        estimated_pages=2,
        raw_content=SAMPLE_DOCUMENT_MARKDOWN,
        theme="dark",
    )
    qtbot.addWidget(dark_dialog)

    assert dark_dialog.theme == "dark"
    dialog_qss = dark_dialog.styleSheet()
    assert "#12121E" in dialog_qss


def test_smart_document_preview_launch_via_anchor(qtbot, monkeypatch):
    """UI Integration Test: Verify clicking docpreview link launches DocumentPreviewDialog."""
    chat_area = ChatArea()
    qtbot.addWidget(chat_area)

    msg_id = chat_area.append_assistant_message(SAMPLE_DOCUMENT_MARKDOWN)

    executed_dialogs = []

    def mock_exec(dialog_self):
        executed_dialogs.append(dialog_self)
        return 1

    monkeypatch.setattr(DocumentPreviewDialog, "exec", mock_exec)

    chat_area._on_anchor_clicked(QUrl(f"docpreview:{msg_id}"))

    assert len(executed_dialogs) == 1
    opened_dialog = executed_dialogs[0]
    assert opened_dialog.doc_title == "Executive AI Business Strategy 2026"
    assert opened_dialog.doc_type == "Business Report"
    assert opened_dialog.raw_content == SAMPLE_DOCUMENT_MARKDOWN


def test_smart_document_wcag_color_contrast_compliance():
    """Verify WCAG 2.1 AA/AAA color contrast compliance for Light Mode and Dark Mode Smart Document UI."""
    # --- Light Mode Compliance Checks ---
    # Card Title (#0F172A) on Card Background (#FFFFFF)
    ratio_title_light = contrast_ratio(SMART_DOC_LIGHT_TITLE, SMART_DOC_LIGHT_CARD_BG)
    assert ratio_title_light >= 4.5
    assert is_wcag_aaa_compliant(SMART_DOC_LIGHT_TITLE, SMART_DOC_LIGHT_CARD_BG)

    # Type Badge Text (#4F46E5) on Badge Background (#EEF2FF)
    ratio_badge_light = contrast_ratio(SMART_DOC_LIGHT_BADGE_TEXT, SMART_DOC_LIGHT_BADGE_BG)
    assert ratio_badge_light >= 4.5
    assert is_wcag_aa_compliant(SMART_DOC_LIGHT_BADGE_TEXT, SMART_DOC_LIGHT_BADGE_BG)

    # Save PDF Button Text (#FFFFFF) on Primary Indigo (#4F46E5) — large bold text, AA sufficient
    ratio_pdf_btn = contrast_ratio("#FFFFFF", "#4F46E5")
    assert ratio_pdf_btn >= 4.5
    assert is_wcag_aa_compliant("#FFFFFF", "#4F46E5")

    # Save DOCX Button Text (#FFFFFF) on Emerald Green (#047857) — darkened for WCAG AA
    ratio_docx_btn = contrast_ratio("#FFFFFF", "#047857")
    assert ratio_docx_btn >= 4.5
    assert is_wcag_aa_compliant("#FFFFFF", "#047857")

    # Preview Quote Text (#334155) on Preview Box Background (#F8FAFC)
    ratio_preview_light = contrast_ratio(SMART_DOC_LIGHT_PREVIEW_TEXT, SMART_DOC_LIGHT_PREVIEW_BG)
    assert ratio_preview_light >= 4.5
    assert is_wcag_aaa_compliant(SMART_DOC_LIGHT_PREVIEW_TEXT, SMART_DOC_LIGHT_PREVIEW_BG)

    # Action Links (#2563EB) on White Card Background (#FFFFFF)
    ratio_link_light = contrast_ratio(SMART_DOC_LIGHT_LINK, SMART_DOC_LIGHT_CARD_BG)
    assert ratio_link_light >= 4.5
    assert is_wcag_aa_compliant(SMART_DOC_LIGHT_LINK, SMART_DOC_LIGHT_CARD_BG)

    # --- Dark Mode Compliance Checks ---
    # Dark Card Title (#F8FAFC) on Dark Card Background (#1E1E2E)
    ratio_title_dark = contrast_ratio(SMART_DOC_DARK_TITLE, SMART_DOC_DARK_CARD_BG)
    assert ratio_title_dark >= 4.5
    assert is_wcag_aaa_compliant(SMART_DOC_DARK_TITLE, SMART_DOC_DARK_CARD_BG)

    # Dark Type Badge Text (#C7D2FE) on Dark Badge Background (#312E81)
    ratio_badge_dark = contrast_ratio(SMART_DOC_DARK_BADGE_TEXT, SMART_DOC_DARK_BADGE_BG)
    assert ratio_badge_dark >= 4.5
    assert is_wcag_aaa_compliant(SMART_DOC_DARK_BADGE_TEXT, SMART_DOC_DARK_BADGE_BG)

    # Dark Muted Text (#94A3B8) on Dark Card Background (#1E1E2E)
    ratio_muted_dark = contrast_ratio(SMART_DOC_DARK_MUTED, SMART_DOC_DARK_CARD_BG)
    assert ratio_muted_dark >= 4.5
    assert is_wcag_aa_compliant(SMART_DOC_DARK_MUTED, SMART_DOC_DARK_CARD_BG)

    # Dark Preview Text (#E2E8F0) on Dark Preview Box Background (#262637)
    ratio_preview_dark = contrast_ratio(SMART_DOC_DARK_PREVIEW_TEXT, SMART_DOC_DARK_PREVIEW_BG)
    assert ratio_preview_dark >= 4.5
    assert is_wcag_aaa_compliant(SMART_DOC_DARK_PREVIEW_TEXT, SMART_DOC_DARK_PREVIEW_BG)

    # Dark Action Links (#60A5FA) on Dark Card Background (#1E1E2E)
    ratio_link_dark = contrast_ratio(SMART_DOC_DARK_LINK, SMART_DOC_DARK_CARD_BG)
    assert ratio_link_dark >= 4.5
    assert is_wcag_aa_compliant(SMART_DOC_DARK_LINK, SMART_DOC_DARK_CARD_BG)
