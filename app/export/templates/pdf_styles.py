"""ReportLab styles and font selection kept separate from PDF export logic."""

from __future__ import annotations

import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def build_pdf_styles() -> dict[str, ParagraphStyle]:
    """Return reusable PDF styles with Bengali-capable font support on Windows."""
    regular_font, bold_font = _register_export_fonts()
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ExportTitle", parent=base["Title"], fontName=bold_font, fontSize=18,
            leading=23, textColor=colors.HexColor("#0B2545"), alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "meta": ParagraphStyle(
            "ExportMeta", parent=base["Normal"], fontName=regular_font, fontSize=8.5,
            leading=11, textColor=colors.HexColor("#4B5563"), spaceAfter=5,
        ),
        "role": ParagraphStyle(
            "ExportRole", parent=base["Heading2"], fontName=bold_font, fontSize=13,
            leading=16, textColor=colors.HexColor("#2E74B5"), spaceBefore=12, spaceAfter=3,
        ),
        "timestamp": ParagraphStyle(
            "ExportTimestamp", parent=base["Normal"], fontName=regular_font, fontSize=8.5,
            leading=11, textColor=colors.HexColor("#6B7280"), spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "ExportBody", parent=base["Normal"], fontName=regular_font, fontSize=10.5,
            leading=15, spaceAfter=7,
        ),
        "code": ParagraphStyle(
            "ExportCode", parent=base["Code"], fontName="Courier", fontSize=8.5,
            leading=11, backColor=colors.HexColor("#F3F4F6"), borderColor=colors.HexColor("#D1D5DB"),
            borderWidth=0.5, borderPadding=6, spaceAfter=8,
        ),
        "attachment": ParagraphStyle(
            "ExportAttachment", parent=base["Normal"], fontName=regular_font, fontSize=9,
            leading=12, leftIndent=12, textColor=colors.HexColor("#374151"), spaceAfter=3,
        ),
    }


def _register_export_fonts() -> tuple[str, str]:
    regular_path, bold_path = _find_bengali_font_paths()
    if regular_path is None:
        # Standard fonts remain usable for Latin-only exports.  The application
        # supplies a clear fallback rather than failing an entire export.
        return "Helvetica", "Helvetica-Bold"

    regular_name = "JakariyaExportRegular"
    bold_name = "JakariyaExportBold"
    if regular_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(regular_name, str(regular_path)))
    if bold_path is not None and bold_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
    return regular_name, bold_name if bold_path is not None else regular_name


def _find_bengali_font_paths() -> tuple[Path | None, Path | None]:
    """Find a Unicode Bengali font without coupling the app to one machine."""
    configured = os.getenv("JAKARIYA_EXPORT_FONT")
    candidates = [Path(configured)] if configured else []

    windir = Path(os.getenv("WINDIR", r"C:\Windows")) / "Fonts"
    candidates.extend([windir / "Nirmala.ttf", windir / "kalpurush.ttf"])

    # Fallback to bundled NotoSansBengali fonts in project assets
    bundled_bld = None
    try:
        from app.utils.paths import get_resource_path
        bundled_reg = get_resource_path("assets", "fonts", "NotoSansBengali-Regular.ttf")
        bundled_bld = get_resource_path("assets", "fonts", "NotoSansBengali-Bold.ttf")
        if bundled_reg.is_file():
            candidates.append(bundled_reg)
    except Exception:
        pass

    regular = next((path for path in candidates if path.is_file()), None)
    if regular is None:
        return None, None

    bold_candidates = []
    if "NotoSansBengali" in regular.name and bundled_bld and bundled_bld.is_file():
        bold_candidates.append(bundled_bld)
    bold_candidates.extend([regular.with_name("NirmalaB.ttf"), regular.with_name("kalpurush Bold.ttf"), regular.with_name("NotoSansBengali-Bold.ttf")])
    bold = next((path for path in bold_candidates if path.is_file()), None)
    return regular, bold
