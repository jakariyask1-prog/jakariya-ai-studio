import re
import html as html_lib
from dataclasses import dataclass

import markdown
from pygments.formatters import HtmlFormatter


# -------------------------------------------------
# Pygments CSS (generated once, reused for every message)
# -------------------------------------------------
#
# css_class must match the "css_class" passed to the codehilite
# extension below (both are "highlight"), otherwise the generated
# selectors won't match the actual <div class="highlight"> wrapper
# codehilite produces.
#
# "friendly" is a light-background style so it blends with the
# ChatArea's white theme instead of clashing like a dark theme would.
_PYGMENTS_FORMATTER = HtmlFormatter(style="friendly", cssclass="highlight")
_PYGMENTS_CSS = _PYGMENTS_FORMATTER.get_style_defs(".highlight")


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
#
# We use a real hyperlink instead of an actual button because QTextEdit
# / QTextBrowser's rich-text engine cannot host interactive widgets
# inside flowing HTML content. A QTextBrowser *does* emit an
# `anchorClicked` signal for `<a href="...">` clicks, which is what
# ChatArea listens to in order to trigger the actual clipboard copy.
#
# IDs must stay unique across the *whole* conversation (not just one
# message), otherwise two code blocks in different messages could both
# render as "copy:0" and clicking the older one would copy the newer
# block's code instead. So `start_id` is passed in by the caller
# (ChatArea keeps a running counter) and the new counter value is
# handed back so the caller can persist it for the next call.

_CODE_BLOCK_PATTERN = re.compile(r'(<div class="highlight">)(.*?)(</div>)', re.DOTALL)
_FENCED_CODE_LANGUAGE_PATTERN = re.compile(r"```(?P<language>[\w+.-]*)[^\n]*\n", re.MULTILINE)

_COPY_BUTTON_STYLE = (
    "color:#4A90E2; text-decoration:none; font-size:9pt; "
    "font-family:'Consolas', monospace; background-color:#EEF3FC; "
    "padding:2px 8px; border:1px solid #D0D7DE; border-radius:4px;"
)


def _inject_copy_buttons(rendered_html: str, start_id: int, languages: list[str]):
    """
    Find every codehilite <div class="highlight"> block in
    `rendered_html`, prepend a "Copy" link to each, and return:

        (new_html, code_map, next_id)

    - new_html:  the HTML with copy-button links inserted
    - code_map:  {block_id: raw_code_text} for the blocks found here
    - next_id:   the next free id, to pass into the following call
    """

    code_map = {}
    counter = [start_id]

    def _replace(match: re.Match) -> str:
        block_id = counter[0]
        counter[0] += 1

        full_block = match.group(0)
        inner = match.group(2)

        # Strip Pygments' <span> highlighting tags to recover the
        # original plain-text code, then unescape HTML entities
        # (&lt;, &amp;, etc.) back to real characters.
        raw_code = re.sub(r"<[^>]+>", "", inner)
        raw_code = html_lib.unescape(raw_code)

        # codehilite always leaves a single trailing newline inside
        # <pre>; drop it so copied code doesn't end with a blank line.
        if raw_code.endswith("\n"):
            raw_code = raw_code[:-1]

        language = languages[len(code_map)] if len(code_map) < len(languages) else ""
        code_map[block_id] = CodeBlock(content=raw_code, language=language)

        copy_link = (
            f'<div style="text-align:right; margin-bottom:2px;">'
            f'<a href="copy:{block_id}" style="{_COPY_BUTTON_STYLE}">'
            f"\U0001F4CB Copy</a> &nbsp; "
            f'<a href="codedownload:{block_id}" style="{_COPY_BUTTON_STYLE}">'
            f"\U0001F4BE Download</a></div>"
        )
        return copy_link + full_block

    new_html = _CODE_BLOCK_PATTERN.sub(_replace, rendered_html)
    return new_html, code_map, counter[0]


@dataclass(frozen=True, slots=True)
class CodeBlock:
    """Raw code and its fenced-code language label for UI actions."""

    content: str
    language: str = ""


def render_markdown(text: str, start_id: int = 0):
    """
    Convert raw markdown text (from Claude's response) into HTML
    that visually matches the ChatArea's light theme (white background,
    black text, Noto Sans Bengali font).

    Fenced code blocks (```python ... ```) are syntax-highlighted using
    Pygments via the markdown "codehilite" extension, and each gets a
    clickable "Copy" link above it (Phase 2.4).

    Args:
        text: raw markdown text to render.
        start_id: first id to assign to a copy button in this message.
            Callers should pass back whatever `next_id` the previous
            call returned, so ids stay unique across the whole chat.

    Returns:
        (html, code_map, next_id) tuple:
            html: fully styled HTML, ready for QTextBrowser.insertHtml()
            code_map: {block_id: raw_code_text} for buttons in this message
            next_id: pass this in as `start_id` for the next render call
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

    # Transform GitHub-style Markdown alerts (> [!NOTE], > [!TIP], > [!WARNING], > [!CAUTION])

    html = re.sub(
        r'<blockquote>\s*<p>\s*\[!NOTE\]\s*',
        '<div style="background-color: #EEF2FF; border-left: 4px solid #4F46E5; border-radius: 0 8px 8px 0; padding: 10px 14px; margin: 12px 0; color: #1E1B4B;">'
        '<b style="color: #4F46E5; font-size: 10pt;">📌 NOTE</b><br>',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r'<blockquote>\s*<p>\s*\[!TIP\]\s*',
        '<div style="background-color: #ECFDF5; border-left: 4px solid #10B981; border-radius: 0 8px 8px 0; padding: 10px 14px; margin: 12px 0; color: #064E3B;">'
        '<b style="color: #059669; font-size: 10pt;">💡 TIP</b><br>',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r'<blockquote>\s*<p>\s*\[!WARNING\]\s*',
        '<div style="background-color: #FFFBEB; border-left: 4px solid #F59E0B; border-radius: 0 8px 8px 0; padding: 10px 14px; margin: 12px 0; color: #78350F;">'
        '<b style="color: #D97706; font-size: 10pt;">⚠️ WARNING</b><br>',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r'<blockquote>\s*<p>\s*\[!(?:CAUTION|IMPORTANT)\]\s*',
        '<div style="background-color: #FEF2F2; border-left: 4px solid #EF4444; border-radius: 0 8px 8px 0; padding: 10px 14px; margin: 12px 0; color: #7F1D1D;">'
        '<b style="color: #DC2626; font-size: 10pt;">🚨 IMPORTANT</b><br>',
        html,
        flags=re.IGNORECASE,
    )

    styled_html = f"""
    <div style="font-family: 'Noto Sans Bengali', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 11.5pt; color: #0F172A; line-height: 1.55; width: 100%; box-sizing: border-box;">
        <style>
            code {{
                background-color: #F1F5F9;
                color: #4F46E5;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                font-size: 10.5pt;
            }}
            pre {{
                background-color: #0F172A;
                border: 1px solid #1E293B;
                padding: 14px;
                border-radius: 8px;
                overflow-x: auto;
                color: #F8FAFC;
                font-size: 10.5pt;
            }}
            pre code {{
                background-color: transparent;
                color: #F8FAFC;
                padding: 0;
            }}
            .highlight {{
                background-color: #0F172A;
                border: 1px solid #1E293B;
                border-radius: 8px;
                padding: 12px;
                margin: 10px 0;
                overflow-x: auto;
                font-family: 'Consolas', monospace;
                font-size: 10.5pt;
                color: #F8FAFC;
            }}
            .highlight pre {{
                background-color: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }}
            {_PYGMENTS_CSS}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 14px;
                margin-bottom: 14px;
                font-size: 11pt;
                border: 1px solid #CBD5E1;
            }}
            th {{
                background-color: #0F172A;
                color: #FFFFFF;
                font-weight: 700;
                padding: 9px 12px;
                border: 1px solid #334155;
                text-align: left;
            }}
            td {{
                border: 1px solid #E2E8F0;
                padding: 8px 12px;
                color: #1E293B;
            }}
            tr:nth-child(even) {{
                background-color: #F8FAFC;
            }}
            blockquote {{
                border-left: 4px solid #4F46E5;
                background-color: #F1F5F9;
                margin: 12px 0;
                padding: 10px 16px;
                border-radius: 0 8px 8px 0;
                color: #1E293B;
            }}
            a {{
                color: #2563EB;
                font-weight: 600;
            }}
        </style>
        {html}
    </div>
    """

    languages = [match.group("language") for match in _FENCED_CODE_LANGUAGE_PATTERN.finditer(text)]
    styled_html, code_map, next_id = _inject_copy_buttons(styled_html, start_id, languages)
    return styled_html, code_map, next_id

