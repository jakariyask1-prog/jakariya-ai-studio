"""DOCX layout tokens for conversation exports (compact reference guide)."""

from __future__ import annotations

from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


def configure_document(document) -> None:
    """Apply the compact-reference-guide tokens to a new DOCX document."""
    section = document.sections[0]
    section.top_margin = section.right_margin = section.bottom_margin = section.left_margin = Inches(1)
    section.header_distance = section.footer_distance = Inches(0.492)

    normal = document.styles["Normal"]
    normal.font.name = "Nirmala UI"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    for name, size, color, before, after in (
        ("Heading 1", 16, "2E74B5", 18, 10),
        ("Heading 2", 13, "2E74B5", 14, 7),
        ("Heading 3", 12, "1F4D78", 10, 5),
    ):
        style = document.styles[name]
        style.font.name = "Nirmala UI"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)

    code_style = document.styles.add_style("Export Code", WD_STYLE_TYPE.PARAGRAPH)
    code_style.font.name = "Courier New"
    code_style.font.size = Pt(9)
    code_style.paragraph_format.space_after = Pt(7)
    code_style.paragraph_format.left_indent = Inches(0.2)


def add_title(document, text: str) -> None:
    """Add a plain title paragraph rather than relying on Word's Title style."""
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(12)
    run = paragraph.add_run(text)
    run.font.name = "Nirmala UI"
    run.font.size = Pt(20)
    run.font.bold = True
    run.font.color.rgb = RGBColor(11, 37, 69)


def set_table_geometry(table, widths_dxa: tuple[int, ...]) -> None:
    """Set fixed, consistent table geometry without Word auto-fit drift."""
    table.autofit = False
    table_pr = table._tbl.tblPr
    table_width = _get_or_add(table_pr, "w:tblW")
    table_width.set(qn("w:w"), str(sum(widths_dxa)))
    table_width.set(qn("w:type"), "dxa")
    table_indent = _get_or_add(table_pr, "w:tblInd")
    table_indent.set(qn("w:w"), "120")
    table_indent.set(qn("w:type"), "dxa")

    for row in table.rows:
        for cell, width in zip(row.cells, widths_dxa, strict=True):
            tc_width = _get_or_add(cell._tc.tcPr, "w:tcW")
            tc_width.set(qn("w:w"), str(width))
            tc_width.set(qn("w:type"), "dxa")


def _get_or_add(parent, tag: str):
    element = parent.find(qn(tag))
    if element is None:
        element = OxmlElement(tag)
        parent.append(element)
    return element
