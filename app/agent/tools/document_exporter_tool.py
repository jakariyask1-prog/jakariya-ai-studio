"""Document Exporter Tool for AI Agent enabling native PDF, DOCX, Excel (.xlsx), HTML, MD, TXT generation with rich multi-color themes."""

import html
import logging
import re
from pathlib import Path
from typing import Dict

from app.agent.tools.base_tool import BaseTool, PermissionLevel, ToolResult
from app.agent.tools.file_tool import resolve_agent_write_path
from app.export.business_logic.markdown_blocks import parse_markdown_blocks

logger = logging.getLogger(__name__)

DOCUMENT_PALETTES: Dict[str, Dict[str, str]] = {
    "vibrant": {
        "title": "#4F46E5",
        "h2": "#7C3AED",
        "h3": "#EC4899",
        "header_bg": "#4F46E5",
        "header_text": "#FFFFFF",
        "alt_row": "#F5F3FF",
        "border": "#C7D2FE",
        "callout_bg": "#EEF2FF",
        "callout_border": "#6366F1",
        "callout_text": "#312E81",
        "accent": "#EC4899",
    },
    "colorful": {
        "title": "#6D28D9",
        "h2": "#2563EB",
        "h3": "#D946EF",
        "header_bg": "#7C3AED",
        "header_text": "#FFFFFF",
        "alt_row": "#FAF5FF",
        "border": "#DDD6FE",
        "callout_bg": "#F5F3FF",
        "callout_border": "#8B5CF6",
        "callout_text": "#4C1D95",
        "accent": "#10B981",
    },
    "emerald": {
        "title": "#065F46",
        "h2": "#059669",
        "h3": "#0D9488",
        "header_bg": "#065F46",
        "header_text": "#FFFFFF",
        "alt_row": "#F0FDF4",
        "border": "#A7F3D0",
        "callout_bg": "#ECFDF5",
        "callout_border": "#10B981",
        "callout_text": "#064E3B",
        "accent": "#0D9488",
    },
    "sunset": {
        "title": "#9A3412",
        "h2": "#E11D48",
        "h3": "#D97706",
        "header_bg": "#C2410C",
        "header_text": "#FFFFFF",
        "alt_row": "#FFF7ED",
        "border": "#FDBA74",
        "callout_bg": "#FFEDD5",
        "callout_border": "#F97316",
        "callout_text": "#7C2D12",
        "accent": "#E11D48",
    },
    "cyber": {
        "title": "#06B6D4",
        "h2": "#F43F5E",
        "h3": "#A855F7",
        "header_bg": "#0F172A",
        "header_text": "#06B6D4",
        "alt_row": "#1E293B",
        "border": "#38BDF8",
        "callout_bg": "#0F172A",
        "callout_border": "#06B6D4",
        "callout_text": "#F8FAFC",
        "accent": "#F43F5E",
    },
    "executive": {
        "title": "#0F172A",
        "h2": "#1E293B",
        "h3": "#4F46E5",
        "header_bg": "#0F172A",
        "header_text": "#FFFFFF",
        "alt_row": "#F8FAFC",
        "border": "#CBD5E1",
        "callout_bg": "#F1F5F9",
        "callout_border": "#4F46E5",
        "callout_text": "#1E293B",
        "accent": "#2563EB",
    },
}


def resolve_doc_palette(theme: str = "") -> Dict[str, str]:
    clean = (theme or "").strip().lower()
    if clean in DOCUMENT_PALETTES:
        return DOCUMENT_PALETTES[clean]
    if any(k in clean for k in ("green", "mint", "tree", "forest", "emerald")):
        return DOCUMENT_PALETTES["emerald"]
    if any(k in clean for k in ("orange", "red", "warm", "sunset", "coral")):
        return DOCUMENT_PALETTES["sunset"]
    if any(k in clean for k in ("cyber", "neon", "dark", "blue", "cyan")):
        return DOCUMENT_PALETTES["cyber"]
    if any(k in clean for k in ("executive", "formal", "corporate", "slate", "black", "gray", "grey")):
        return DOCUMENT_PALETTES["executive"]
    if any(k in clean for k in ("colorful", "purple", "violet", "magenta")):
        return DOCUMENT_PALETTES["colorful"]
    if any(k in clean for k in ("color", "rainbow", "multi", "vibrant", "style", "pretty", "fancy")):
        return DOCUMENT_PALETTES["vibrant"]
    return DOCUMENT_PALETTES["vibrant"]  # Default to vibrant multi-color theme for stylish documents!


class DocumentExporterTool(BaseTool):
    """Tool enabling AI Agent to generate and export physical PDF, DOCX, Excel (.xlsx), HTML, Markdown, and Text files."""

    def __init__(self):
        super().__init__(
            name="export_document",
            description="Create and save physical document files (.pdf, .docx, .xlsx, .html, .md, .txt, .csv, .json) with vibrant multi-color combinations and styled themes to local disk.",
            permission_level=PermissionLevel.REQUIRES_APPROVAL,
            version="2.1.0",
            supported_file_types=[".pdf", ".docx", ".xlsx", ".html", ".md", ".txt", ".csv", ".json"],
            capabilities=["export_document", "pdf_generator", "docx_generator", "excel_generator", "file_export"],
            input_schema={
                "file_path": "string",
                "content": "string",
                "title": "string (optional)",
                "theme": "string (optional: colorful, vibrant, emerald, sunset, cyber, executive)",
            },
            output_schema={"message": "string", "saved_path": "string"},
        )

    def execute(self, file_path: str = "", content: str = "", title: str = "Document Report", **kwargs) -> ToolResult:
        if not file_path or not file_path.strip():
            return ToolResult(success=False, output="", error="file_path parameter is required.")

        p = resolve_agent_write_path(file_path)
        ext = p.suffix.lower()

        if ext not in self.metadata.supported_file_types:
            supported = ", ".join(self.metadata.supported_file_types)
            return ToolResult(
                success=False,
                output="",
                error=f"Unsupported document type '{ext or '[no extension]'}'. Supported types: {supported}.",
            )

        theme_name = str(kwargs.get("theme") or kwargs.get("color_palette") or kwargs.get("color") or kwargs.get("style") or "colorful")
        palette = resolve_doc_palette(theme_name)

        try:
            p.parent.mkdir(parents=True, exist_ok=True)

            if ext == ".pdf":
                self._generate_pdf(p, title, content, palette=palette)
            elif ext == ".docx":
                self._generate_docx(p, title, content, palette=palette)
            elif ext == ".xlsx":
                self._generate_excel(p, title, content, theme=theme_name)
            elif ext == ".html":
                self._generate_html(p, title, content, palette=palette)
            else:
                p.write_text(content, encoding="utf-8")

            # Mirror to real Windows Shell Desktop if saved to home / Desktop and distinct
            from app.agent.tools.file_tool import get_windows_shell_folder, _is_within
            shell_desktop = get_windows_shell_folder("Desktop")
            if (
                shell_desktop
                and shell_desktop.exists()
                and _is_within(p, Path.home() / "Desktop")
                and not _is_within(p, shell_desktop)
            ):
                try:
                    import shutil
                    rel = p.relative_to(Path.home() / "Desktop")
                    mirror_target = shell_desktop / rel
                    mirror_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, mirror_target)
                except Exception:
                    pass

            abs_path = str(p.resolve())
            msg = f"Successfully generated and saved physical document with '{theme_name}' multi-color theme to: {abs_path}"
            logger.info("[DocumentExporterTool] %s", msg)
            return ToolResult(success=True, output=msg, data={"saved_path": abs_path})

        except Exception as exc:
            err = f"Failed to generate {ext} document: {exc}"
            logger.error("[DocumentExporterTool] %s", err, exc_info=True)
            return ToolResult(success=False, output="", error=err)

    def _generate_excel(self, path: Path, title: str, content: str, theme: str = "colorful") -> None:
        """Generate styled Excel spreadsheet (.xlsx) using ExcelExporter."""
        from app.export.business_logic.excel_exporter import ExcelExporter

        ExcelExporter.create_excel_from_markdown(content, path, title=title, theme=theme)

    def _generate_pdf(self, path: Path, title: str, content: str, palette: Dict[str, str] = None) -> None:
        """Generate multi-colored PDF document with rich ReportLab styles, multi-color headings, and formatted tables."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

        if palette is None:
            palette = resolve_doc_palette("colorful")

        doc = SimpleDocTemplate(
            str(path),
            pagesize=letter,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )
        styles = getSampleStyleSheet()

        lines = [l.strip() for l in content.splitlines() if l.strip()]
        doc_title = title
        if title.strip().lower() in ("document report", "", "document") and lines:
            first_line = lines[0].lstrip("#").strip()
            if first_line:
                doc_title = first_line

        from app.export.templates.pdf_styles import _register_export_fonts
        regular_font, bold_font = _register_export_fonts()

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor(palette["title"]),
            spaceAfter=12,
            fontName=bold_font,
        )

        h1_style = ParagraphStyle(
            "DocH1",
            parent=styles["Heading1"],
            fontSize=15,
            leading=19,
            textColor=colors.HexColor(palette["title"]),
            spaceBefore=12,
            spaceAfter=6,
            fontName=bold_font,
        )

        h2_style = ParagraphStyle(
            "DocH2",
            parent=styles["Heading2"],
            fontSize=13,
            leading=17,
            textColor=colors.HexColor(palette["h2"]),
            spaceBefore=10,
            spaceAfter=6,
            fontName=bold_font,
        )

        h3_style = ParagraphStyle(
            "DocH3",
            parent=styles["Heading3"],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor(palette["h3"]),
            spaceBefore=8,
            spaceAfter=4,
            fontName=bold_font,
        )

        body_style = ParagraphStyle(
            "DocBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14.5,
            textColor=colors.HexColor("#334155"),
            spaceAfter=6,
            fontName=regular_font,
        )

        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor(palette["header_text"]),
            fontName=bold_font,
            alignment=1,  # Center
        )

        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
            fontName=regular_font,
        )

        code_style = ParagraphStyle(
            "DocCode",
            parent=styles["Code"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#F8FAFC"),
            backColor=colors.HexColor("#0F172A"),
            borderPadding=6,
            spaceAfter=8,
        )

        callout_style = ParagraphStyle(
            "DocCallout",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor(palette["callout_text"]),
            backColor=colors.HexColor(palette["callout_bg"]),
            borderColor=colors.HexColor(palette["callout_border"]),
            borderWidth=1,
            borderPadding=8,
            spaceBefore=6,
            spaceAfter=8,
        )

        def _to_reportlab_markup(text: str) -> str:
            escaped = html.escape(text).replace("\n", "<br/>")
            escaped = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)
            escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
            escaped = re.sub(r"(?<!\*)\*([^*]+)\*", r"<i>\1</i>", escaped)
            return escaped

        story = [Paragraph(_to_reportlab_markup(doc_title), title_style), Spacer(1, 6)]

        blocks = parse_markdown_blocks(content)
        for block in blocks:
            if block.kind == "code":
                story.append(Preformatted(block.text, code_style))
                story.append(Spacer(1, 4))

            elif block.kind == "table" and block.rows:
                table_data = []
                for r_idx, row in enumerate(block.rows):
                    row_cells = []
                    for cell_text in row:
                        cell_markup = _to_reportlab_markup(cell_text)
                        style = table_header_style if r_idx == 0 else table_cell_style
                        row_cells.append(Paragraph(cell_markup, style))
                    table_data.append(row_cells)

                if table_data:
                    col_count = max(len(r) for r in table_data)
                    col_width = (7.5 * inch) / col_count
                    pdf_table = Table(table_data, colWidths=[col_width] * col_count, repeatRows=1, hAlign="LEFT")

                    t_style = [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(palette["header_bg"])),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(palette["border"])),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ]
                    for r_idx in range(1, len(table_data)):
                        bg_hex = palette["alt_row"] if r_idx % 2 == 1 else "#FFFFFF"
                        t_style.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor(bg_hex)))

                    pdf_table.setStyle(TableStyle(t_style))
                    story.append(pdf_table)
                    story.append(Spacer(1, 8))

            else:
                for para in block.text.split("\n\n"):
                    para_clean = para.strip()
                    if not para_clean:
                        continue

                    if doc_title and (para_clean == doc_title or para_clean.lstrip("#").strip() == doc_title):
                        continue

                    heading_match = re.match(r"^(#{1,3})\s+(.+)$", para_clean)
                    if heading_match and "\n" not in para_clean:
                        h_level = len(heading_match.group(1))
                        h_style = h1_style if h_level == 1 else (h2_style if h_level == 2 else h3_style)
                        story.append(Paragraph(_to_reportlab_markup(heading_match.group(2).strip()), h_style))
                        story.append(Spacer(1, 3))
                        continue

                    if para_clean.startswith(">"):
                        quote_text = para_clean.lstrip("> ").strip()
                        story.append(Paragraph(_to_reportlab_markup(quote_text), callout_style))
                        continue

                    story.append(Paragraph(_to_reportlab_markup(para_clean), body_style))
                    story.append(Spacer(1, 4))

        def _add_page_number(canvas, doc_obj):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#64748B"))
            canvas.drawRightString(letter[0] - 36, 20, f"Page {doc_obj.page}")
            canvas.restoreState()

        doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)

    def _generate_docx(self, path: Path, title: str, content: str, palette: Dict[str, str] = None) -> None:
        """Generate DOCX document with vibrant multi-color headers, formatted tables, cell shading, and callout blocks."""
        import docx
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement, parse_xml
        from docx.oxml.ns import nsdecls, qn

        if palette is None:
            palette = resolve_doc_palette("colorful")

        doc = docx.Document()

        def _hex_to_rgb(hex_str: str) -> docx.shared.RGBColor:
            clean = hex_str.lstrip("#")
            return docx.shared.RGBColor(*(int(clean[i : i + 2], 16) for i in (0, 2, 4)))

        lines = [l.strip() for l in content.splitlines() if l.strip()]
        doc_title = title
        if title.strip().lower() in ("document report", "", "document") and lines:
            first_line = lines[0].lstrip("#").strip()
            if first_line:
                doc_title = first_line

        if doc_title:
            h = doc.add_heading(level=0)
            h.alignment = WD_ALIGN_PARAGRAPH.LEFT
            r = h.add_run(doc_title)
            r.font.color.rgb = _hex_to_rgb(palette["title"])

        def _set_cell_bg(cell, hex_color):
            tcPr = cell._tc.get_or_add_tcPr()
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color.lstrip("#")}"/>')
            tcPr.append(shd)

        def _set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
            tcPr = cell._tc.get_or_add_tcPr()
            tcMar = OxmlElement("w:tcMar")
            for m, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
                node = OxmlElement(f"w:{m}")
                node.set(qn("w:w"), str(val))
                node.set(qn("w:type"), "dxa")
                tcMar.append(node)
            tcPr.append(tcMar)

        blocks = parse_markdown_blocks(content)
        for block in blocks:
            if block.kind == "code":
                p = doc.add_paragraph()
                p.paragraph_format.space_before = docx.shared.Pt(4)
                p.paragraph_format.space_after = docx.shared.Pt(6)
                run = p.add_run(block.text)
                run.font.name = "Courier New"
                run.font.size = docx.shared.Pt(9.5)
                run.font.color.rgb = docx.shared.RGBColor(15, 23, 42)
                continue

            if block.kind == "table" and block.rows:
                col_count = max(len(r) for r in block.rows)
                table = doc.add_table(rows=len(block.rows), cols=col_count)
                table.style = "Table Grid"

                for r_idx, row in enumerate(block.rows):
                    for c_idx, val in enumerate(row):
                        cell = table.cell(r_idx, c_idx)
                        cell.text = val
                        _set_cell_margins(cell, top=100, bottom=100, left=140, right=140)

                        if r_idx == 0:
                            _set_cell_bg(cell, palette["header_bg"])
                            for run in cell.paragraphs[0].runs:
                                run.bold = True
                                run.font.color.rgb = _hex_to_rgb(palette["header_text"])
                                run.font.name = "Segoe UI"
                        else:
                            bg_hex = palette["alt_row"] if r_idx % 2 == 1 else "FFFFFF"
                            _set_cell_bg(cell, bg_hex)
                            for run in cell.paragraphs[0].runs:
                                run.font.color.rgb = docx.shared.RGBColor(51, 65, 85)
                                run.font.name = "Segoe UI"
                continue

            for line in block.text.splitlines():
                clean_line = line.strip()
                if not clean_line:
                    continue

                if doc_title and (clean_line == doc_title or clean_line.lstrip("#").strip() == doc_title):
                    continue

                heading_match = re.match(r"^(#{1,3})\s+(.+)$", clean_line)
                if heading_match:
                    level = len(heading_match.group(1))
                    h = doc.add_heading(level=level)
                    r = h.add_run(heading_match.group(2).strip())
                    color_hex = palette["title"] if level == 1 else (palette["h2"] if level == 2 else palette["h3"])
                    r.font.color.rgb = _hex_to_rgb(color_hex)
                    continue

                if clean_line.startswith(">"):
                    p = doc.add_paragraph()
                    p.paragraph_format.left_indent = docx.shared.Inches(0.3)
                    run = p.add_run(clean_line.lstrip("> ").strip())
                    run.italic = True
                    run.font.color.rgb = _hex_to_rgb(palette["callout_border"])
                    continue

                p = doc.add_paragraph()
                pattern = re.compile(r"(\*\*.+?\*\*|`.+?`|(?<!\*)\*[^*]+\*)", re.DOTALL)
                for part in pattern.split(clean_line):
                    if not part:
                        continue
                    run = p.add_run(part.strip("*`"))
                    if part.startswith("**"):
                        run.bold = True
                    elif part.startswith("`"):
                        run.font.name = "Courier New"
                    elif part.startswith("*"):
                        run.italic = True

        doc.save(str(path))

    def _generate_html(self, path: Path, title: str, content: str, palette: Dict[str, str] = None) -> None:
        """Generate styled responsive HTML document with CSS multi-color variables, tables, and callouts."""
        import markdown

        if palette is None:
            palette = resolve_doc_palette("colorful")

        html_body = markdown.markdown(content, extensions=["tables", "fenced_code", "codehilite"])
        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
        :root {{
            --bg: #f8fafc;
            --surface: #ffffff;
            --text: #1e293b;
            --primary: {palette["title"]};
            --secondary: {palette["h2"]};
            --accent: {palette["accent"]};
            --header-bg: {palette["header_bg"]};
            --header-text: {palette["header_text"]};
            --alt-row: {palette["alt_row"]};
            --border: {palette["border"]};
            --callout-bg: {palette["callout_bg"]};
            --callout-border: {palette["callout_border"]};
            --code-bg: #0f172a;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            max-width: 920px;
            margin: 40px auto;
            padding: 24px;
            color: var(--text);
            background: var(--bg);
        }}
        .document-card {{
            background: var(--surface);
            padding: 36px 44px;
            border-radius: 14px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.04);
            border: 1.5px solid var(--border);
        }}
        h1 {{ color: var(--primary); border-bottom: 3px solid var(--primary); padding-bottom: 12px; margin-top: 0; font-size: 2.2rem; }}
        h2 {{ color: var(--secondary); margin-top: 28px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
        h3 {{ color: var(--accent); margin-top: 20px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 24px 0;
            font-size: 0.95rem;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--border);
        }}
        th {{
            background: var(--header-bg);
            color: var(--header-text);
            font-weight: 700;
            padding: 14px 16px;
            text-align: left;
        }}
        td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
        }}
        tr:nth-child(even) {{ background: var(--alt-row); }}
        code {{ background: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 0.9em; }}
        pre {{ background: var(--code-bg); color: #f8fafc; padding: 18px; border-radius: 10px; overflow-x: auto; }}
        blockquote {{
            border-left: 5px solid var(--callout-border);
            margin: 20px 0;
            padding: 12px 20px;
            background: var(--callout-bg);
            color: var(--primary);
            border-radius: 0 10px 10px 0;
            font-size: 1.02em;
        }}
    </style>
</head>
<body>
    <div class="document-card">
        <h1>{html.escape(title)}</h1>
        {html_body}
    </div>
</body>
</html>"""
        path.write_text(html_doc, encoding="utf-8")
