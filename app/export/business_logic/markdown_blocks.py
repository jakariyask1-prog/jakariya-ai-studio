"""Small, dependency-free parser for the Markdown blocks used in exports."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MarkdownBlock:
    """One paragraph, fenced code block, or pipe table from a message."""

    kind: str
    text: str = ""
    language: str = ""
    rows: tuple[tuple[str, ...], ...] = ()


_FENCE_PATTERN = re.compile(r"^```(?P<language>[\w+-]*)\s*$")
_TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$")


def parse_markdown_blocks(content: str) -> tuple[MarkdownBlock, ...]:
    """Parse common chat Markdown while preserving unknown syntax as text."""
    blocks: list[MarkdownBlock] = []
    text_lines: list[str] = []
    code_lines: list[str] = []
    code_language = ""
    in_code_block = False

    def flush_text() -> None:
        nonlocal text_lines
        if text_lines:
            blocks.extend(_parse_text_blocks("\n".join(text_lines).strip("\n")))
            text_lines = []

    for line in content.splitlines():
        match = _FENCE_PATTERN.match(line)
        if match:
            if in_code_block:
                blocks.append(
                    MarkdownBlock("code", "\n".join(code_lines), code_language)
                )
                code_lines = []
                code_language = ""
                in_code_block = False
            else:
                flush_text()
                code_language = match.group("language")
                in_code_block = True
            continue
        if in_code_block:
            code_lines.append(line)
        else:
            text_lines.append(line)

    if in_code_block:
        # An unfinished fence is still exported as code rather than discarded.
        blocks.append(MarkdownBlock("code", "\n".join(code_lines), code_language))
    else:
        flush_text()
    return tuple(blocks)


def _parse_text_blocks(text: str) -> list[MarkdownBlock]:
    if not text:
        return []

    lines = text.splitlines()
    blocks: list[MarkdownBlock] = []
    paragraph_lines: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        paragraph = "\n".join(paragraph_lines).strip()
        if paragraph:
            blocks.append(MarkdownBlock("paragraph", paragraph))
        paragraph_lines = []

    while index < len(lines):
        if (
            index + 1 < len(lines)
            and _is_table_row(lines[index])
            and _TABLE_SEPARATOR_PATTERN.match(lines[index + 1])
        ):
            flush_paragraph()
            table_lines = [lines[index]]
            index += 2
            while index < len(lines) and _is_table_row(lines[index]):
                table_lines.append(lines[index])
                index += 1
            blocks.append(MarkdownBlock("table", rows=tuple(_split_table_row(line) for line in table_lines)))
            continue
        paragraph_lines.append(lines[index])
        index += 1
    flush_paragraph()
    return blocks


def _is_table_row(line: str) -> bool:
    return "|" in line and line.strip().startswith("|")


def _split_table_row(line: str) -> tuple[str, ...]:
    return tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
