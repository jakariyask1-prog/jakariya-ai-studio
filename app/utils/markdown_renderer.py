import re
import html as html_lib
from dataclasses import dataclass

import markdown
from pygments.formatters import HtmlFormatter


# -------------------------------------------------
# Pygments CSS (Light and Dark Themes)
# -------------------------------------------------
_PYGMENTS_FORMATTER_LIGHT = HtmlFormatter(style="friendly", cssclass="highlight")
_PYGMENTS_CSS_LIGHT = _PYGMENTS_FORMATTER_LIGHT.get_style_defs(".highlight")

_PYGMENTS_FORMATTER_DARK = HtmlFormatter(style="one-dark", cssclass="highlight")
_PYGMENTS_CSS_DARK = _PYGMENTS_FORMATTER_DARK.get_style_defs(".highlight")


# -------------------------------------------------
# Copy Button Injection (Phase 2.4)
# -------------------------------------------------
#
# codehilite wraps every fenced code block in a
# <div class="highlight">...</div>. We find each one *after* markdown
# has already rendered it, strip the Pygments <span> tags back out to
# recover the original plain-text code, and stash that raw text in a
# dict keyed by a small integer id. A "Copy" hyperlink referencing that
# id (href="copy:<id>") is inserted directly above the block.

_CODE_BLOCK_PATTERN = re.compile(r'(<div class="highlight">)(.*?)(</div>)', re.DOTALL)
_FENCED_CODE_LANGUAGE_PATTERN = re.compile(r"```(?P<language>[\w+.-]*)[^\n]*\n", re.MULTILINE)


def _inject_copy_buttons(rendered_html: str, start_id: int, languages: list[str], theme: str = "light"):
    """
    Find every codehilite <div class="highlight"> block in
    `rendered_html`, prepend a sleek header bar with language and action buttons.
    """
    code_map = {}
    counter = [start_id]
    is_dark = str(theme).lower() in ("dark", "oled", "neon")

    header_bg = "#111827" if is_dark else "#1E293B"
    header_border = "#1F2937" if is_dark else "#334155"
    lang_color = "#9CA3AF" if is_dark else "#94A3B8"
    btn_bg = "#1F2937" if is_dark else "#334155"
    btn_color = "#E5E7EB" if is_dark else "#CBD5E1"

    def _replace(match: re.Match) -> str:
        block_id = counter[0]
        counter[0] += 1

        full_block = match.group(0)
        inner = match.group(2)

        # Strip Pygments' <span> highlighting tags to recover the original plain-text code
        raw_code = re.sub(r"<[^>]+>", "", inner)
        raw_code = html_lib.unescape(raw_code)

        if raw_code.endswith("\n"):
            raw_code = raw_code[:-1]

        language = languages[len(code_map)] if len(code_map) < len(languages) else ""
        code_map[block_id] = CodeBlock(content=raw_code, language=language)

        lang_label = html_lib.escape((language or "code").upper())

        header_bar = (
            f'<table width="100%" cellspacing="0" cellpadding="0" style="margin-top:10px; margin-bottom:0px; '
            f'background-color:{header_bg}; border:1px solid {header_border}; border-bottom:none; '
            f'border-radius:8px 8px 0 0; padding:5px 12px;">'
            f'<tr>'
            f'<td align="left"><span style="color:{lang_color}; font-size:8.5pt; font-family:\'Segoe UI Variable\', sans-serif; font-weight:700; letter-spacing:0.5px;">💻 {lang_label}</span></td>'
            f'<td align="right">'
            f'<a href="copy:{block_id}" style="color:{btn_color}; text-decoration:none; font-size:8.5pt; font-family:\'Segoe UI Variable\', sans-serif; background-color:{btn_bg}; padding:3px 10px; border-radius:5px; font-weight:600; margin-right:6px;">📋 Copy</a>'
            f'<a href="codedownload:{block_id}" style="color:{btn_color}; text-decoration:none; font-size:8.5pt; font-family:\'Segoe UI Variable\', sans-serif; background-color:{btn_bg}; padding:3px 10px; border-radius:5px; font-weight:600;">💾 Download</a>'
            f'</td>'
            f'</tr></table>'
        )
        return header_bar + full_block

    new_html = _CODE_BLOCK_PATTERN.sub(_replace, rendered_html)
    return new_html, code_map, counter[0]


@dataclass(frozen=True, slots=True)
class CodeBlock:
    """Raw code and its fenced-code language label for UI actions."""

    content: str
    language: str = ""


def render_markdown(text: str, start_id: int = 0, theme: str = "light"):
    """
    Convert raw markdown text into HTML dynamically styled for *theme*
    (light, dark, oled, neon) with high-contrast typography and syntax highlighting.
    """
    html = markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "nl2br", "sane_lists", "codehilite"],
        extension_configs={
            "codehilite": {
                "css_class": "highlight",
                "guess_lang": False,
                "noclasses": False,
            }
        },
    )

    theme_str = str(theme).lower()
    is_dark = theme_str in ("dark", "oled", "neon")
    is_oled = theme_str == "oled"
    is_neon = theme_str == "neon"

    # Theme-adaptive GitHub-style Markdown alerts
    if is_dark:
        note_bg, note_border, note_title, note_fg = "#1E1B4B", "#6366F1", "#818CF8", "#E0E7FF"
        tip_bg, tip_border, tip_title, tip_fg = "#064E3B", "#10B981", "#34D399", "#D1FAE5"
        warn_bg, warn_border, warn_title, warn_fg = "#451A03", "#F59E0B", "#FBBF24", "#FEF3C7"
        alert_bg, alert_border, alert_title, alert_fg = "#450A0A", "#EF4444", "#F87171", "#FEE2E2"
    else:
        note_bg, note_border, note_title, note_fg = "#EEF2FF", "#4F46E5", "#4F46E5", "#1E1B4B"
        tip_bg, tip_border, tip_title, tip_fg = "#ECFDF5", "#10B981", "#059669", "#064E3B"
        warn_bg, warn_border, warn_title, warn_fg = "#FFFBEB", "#F59E0B", "#D97706", "#78350F"
        alert_bg, alert_border, alert_title, alert_fg = "#FEF2F2", "#EF4444", "#DC2626", "#7F1D1D"

    html = re.sub(
        r'<blockquote>\s*<p>\s*\[!NOTE\]\s*',
        f'<div style="background-color: {note_bg}; border-left: 4px solid {note_border}; border-radius: 0 8px 8px 0; padding: 10px 14px; margin: 12px 0; color: {note_fg};">'
        f'<b style="color: {note_title}; font-size: 10pt;">📌 NOTE</b><br>',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r'<blockquote>\s*<p>\s*\[!TIP\]\s*',
        f'<div style="background-color: {tip_bg}; border-left: 4px solid {tip_border}; border-radius: 0 8px 8px 0; padding: 10px 14px; margin: 12px 0; color: {tip_fg};">'
        f'<b style="color: {tip_title}; font-size: 10pt;">💡 TIP</b><br>',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r'<blockquote>\s*<p>\s*\[!WARNING\]\s*',
        f'<div style="background-color: {warn_bg}; border-left: 4px solid {warn_border}; border-radius: 0 8px 8px 0; padding: 10px 14px; margin: 12px 0; color: {warn_fg};">'
        f'<b style="color: {warn_title}; font-size: 10pt;">⚠️ WARNING</b><br>',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r'<blockquote>\s*<p>\s*\[!(?:CAUTION|IMPORTANT)\]\s*',
        f'<div style="background-color: {alert_bg}; border-left: 4px solid {alert_border}; border-radius: 0 8px 8px 0; padding: 10px 14px; margin: 12px 0; color: {alert_fg};">'
        f'<b style="color: {alert_title}; font-size: 10pt;">🚨 IMPORTANT</b><br>',
        html,
        flags=re.IGNORECASE,
    )

    # Theme colors for typography, code, and tables
    if is_dark:
        main_text_color = "#FFFFFF" if is_oled else ("#F8FAFC" if is_neon else "#ECECF1")
        inline_code_bg = "#121212" if is_oled else ("#1E293B" if is_neon else "#2F2F2F")
        inline_code_fg = "#F472B6" if is_neon else "#A5B4FC"
        inline_code_border = "#334155" if is_neon else "#3E3E3E"
        code_block_bg = "#0B0F19" if is_dark else "#0F172A"
        code_block_border = "#1F2937" if is_dark else "#1E293B"
        table_th_bg = "#1E293B"
        table_th_fg = "#F8FAFC"
        table_th_border = "#334155"
        table_td_border = "#262626" if is_oled else "#2F2F2F"
        table_td_color = main_text_color
        table_tr_even = "#0A0A0A" if is_oled else "#262626"
        quote_bg = "#141414" if is_oled else "#262626"
        quote_border = "#F472B6" if is_neon else "#6366F1"
        link_color = "#F472B6" if is_neon else "#10B981"
        pygments_css = _PYGMENTS_CSS_DARK
    else:
        main_text_color = "#0F172A"
        inline_code_bg = "#F1F5F9"
        inline_code_fg = "#4F46E5"
        inline_code_border = "#E2E8F0"
        code_block_bg = "#0F172A"
        code_block_border = "#1E293B"
        table_th_bg = "#0F172A"
        table_th_fg = "#FFFFFF"
        table_th_border = "#334155"
        table_td_border = "#E2E8F0"
        table_td_color = "#1E293B"
        table_tr_even = "#F8FAFC"
        quote_bg = "#F8FAFC"
        quote_border = "#4F46E5"
        link_color = "#10A37F"
        pygments_css = _PYGMENTS_CSS_LIGHT

    styled_html = f"""
    <div style="font-family: 'Segoe UI Variable', 'Noto Sans Bengali', 'Inter', system-ui, sans-serif; font-size: 11.5pt; color: {main_text_color}; line-height: 1.6; width: 100%; box-sizing: border-box;">
        <style>
            code {{
                background-color: {inline_code_bg};
                color: {inline_code_fg};
                border: 1px solid {inline_code_border};
                padding: 2px 6px;
                border-radius: 4px;
                font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
                font-size: 10pt;
            }}
            pre {{
                background-color: {code_block_bg};
                border: 1px solid {code_block_border};
                padding: 14px;
                border-radius: 8px;
                overflow-x: auto;
                color: #F8FAFC;
                font-size: 10pt;
                font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
            }}
            pre code {{
                background-color: transparent;
                border: none;
                color: #F8FAFC;
                padding: 0;
            }}
            .highlight {{
                background-color: {code_block_bg};
                border: 1px solid {code_block_border};
                border-top: none;
                border-radius: 0 0 8px 8px;
                padding: 12px 14px;
                margin-top: 0px;
                margin-bottom: 12px;
                overflow-x: auto;
                font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
                font-size: 10pt;
                color: #F8FAFC;
            }}
            .highlight pre {{
                background-color: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }}
            {pygments_css}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 14px;
                margin-bottom: 14px;
                font-size: 10.5pt;
                border: 1px solid {table_td_border};
            }}
            th {{
                background-color: {table_th_bg};
                color: {table_th_fg};
                font-weight: 700;
                padding: 8px 12px;
                border: 1px solid {table_th_border};
                text-align: left;
            }}
            td {{
                border: 1px solid {table_td_border};
                padding: 8px 12px;
                color: {table_td_color};
            }}
            tr:nth-child(even) {{
                background-color: {table_tr_even};
            }}
            blockquote {{
                border-left: 4px solid {quote_border};
                background-color: {quote_bg};
                margin: 12px 0;
                padding: 10px 16px;
                border-radius: 0 8px 8px 0;
                color: {main_text_color};
            }}
            a {{
                color: {link_color};
                font-weight: 600;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
        </style>
        {html}
    </div>
    """

    languages = [match.group("language") for match in _FENCED_CODE_LANGUAGE_PATTERN.finditer(text)]
    styled_html, code_map, next_id = _inject_copy_buttons(styled_html, start_id, languages, theme=theme_str)
    return styled_html, code_map, next_id
