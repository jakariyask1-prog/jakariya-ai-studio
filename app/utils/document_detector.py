"""Smart Document Detection & Analysis Engine for Claude Desktop-style Document Cards."""

import re
import math
from dataclasses import dataclass


@dataclass
class DetectedDocument:
    """Dataclass holding extracted metadata for a detected structured document."""

    is_document: bool
    title: str
    document_type: str
    preview_text: str
    word_count: int
    estimated_pages: int
    has_tables: bool
    raw_content: str


class DocumentDetector:
    """Detects if AI response text qualifies as a structured document, report, table, or roadmap."""

    @staticmethod
    def detect(text: str) -> DetectedDocument:
        raw_text = text or ""
        clean_text = raw_text.strip()
        
        # Word count calculation
        words = re.findall(r"\b\w+\b", clean_text)
        word_count = len(words)
        
        # Page count estimation (~250 words per page)
        estimated_pages = max(1, math.ceil(word_count / 250)) if word_count > 0 else 1
        
        # Table detection
        has_tables = bool(re.search(r"\|[^\n]+\|\n\|[-:\s|]+\|\n\|[^\n]+\|", clean_text))
        
        # Heading detection
        h1_match = re.search(r"^#\s+(.*)", clean_text, re.MULTILINE)
        h2_match = re.search(r"^##\s+(.*)", clean_text, re.MULTILINE)
        
        title = "Untitled Document"
        if h1_match:
            title = h1_match.group(1).strip(" *#`")
        elif h2_match:
            title = h2_match.group(1).strip(" *#`")
        else:
            # Fallback title from first line
            first_line = clean_text.split("\n")[0].strip()
            if first_line and len(first_line) <= 60:
                title = first_line.strip(" *#`")

        # Clean leading document emojis and markdown decorators
        title = re.sub(r"^[\U00010000-\U0010ffff\u2600-\u27ff\u2b50\u2b55\u231a-\u23ff\u200d\ufe0f\s*#`:\-\|]+", "", title).strip() or title

        # Document Type classification
        lower_text = clean_text.lower()
        if "roadmap" in lower_text or "timeline" in lower_text or "phase 1" in lower_text:
            doc_type = "Project Roadmap"
        elif "report" in lower_text or "executive summary" in lower_text or "analysis" in lower_text:
            doc_type = "Business Report"
        elif has_tables and word_count < 300:
            doc_type = "Data Table"
        elif "proposal" in lower_text or "plan" in lower_text or "overview" in lower_text:
            doc_type = "Strategic Plan"
        elif "python" in lower_text or "code" in lower_text or "script" in lower_text:
            doc_type = "Technical Document"
        else:
            doc_type = "Markdown Document"

        heading_count = len(re.findall(r"^#{1,3}\s+.+", clean_text, re.MULTILINE))
        has_document_keyword = bool(re.search(
            r"\b(report|proposal|roadmap|plan|strategy|summary|document|analysis|timeline|invoice)\b",
            lower_text,
        ))

        # Document criteria:
        # 1. Long generated content is always a document.
        # 2. A compact, clearly structured Markdown document deserves a card too.
        # 3. Tables are valuable documents even when the surrounding prose is brief.
        # Ordinary short chat messages do not satisfy any of these signals.
        is_doc = (
            word_count >= 120
            or (heading_count >= 2 and word_count >= 20)
            or (bool(h1_match or h2_match) and has_document_keyword and word_count >= 20)
            or (has_tables and word_count >= 10)
        )

        # Generate clean 2-3 line preview text
        lines = [line.strip() for line in clean_text.split("\n") if line.strip() and not line.strip().startswith("#")]
        preview_lines = lines[:3]
        preview_text = " ".join(preview_lines)
        if len(preview_text) > 180:
            preview_text = preview_text[:177] + "..."

        return DetectedDocument(
            is_document=is_doc,
            title=title,
            document_type=doc_type,
            preview_text=preview_text,
            word_count=word_count,
            estimated_pages=estimated_pages,
            has_tables=has_tables,
            raw_content=clean_text,
        )
