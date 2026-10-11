"""Document Chunking Service for RAG Vector Search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """A segment of an extracted document with metadata."""

    text: str
    source_name: str
    chunk_index: int
    start_char: int
    end_char: int


class DocumentChunker:
    """Split document text into overlapping segments preserving semantic context."""

    def __init__(self, chunk_size: int = 800, overlap: int = 100):
        self.chunk_size = max(100, chunk_size)
        self.overlap = min(self.chunk_size // 2, max(0, overlap))

    def chunk_document(self, text: str, source_name: str) -> List[DocumentChunk]:
        """Split text into overlapping chunks while respecting paragraph boundaries where possible."""
        clean_text = text.strip()
        if not clean_text:
            return []

        chunks: List[DocumentChunk] = []
        text_length = len(clean_text)
        start = 0
        chunk_idx = 0

        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            # Try to snap end boundary to the nearest paragraph break or line break if available
            if end < text_length:
                break_pos = clean_text.rfind("\n\n", start + self.overlap, end)
                if break_pos == -1:
                    break_pos = clean_text.rfind("\n", start + self.overlap, end)
                if break_pos == -1:
                    break_pos = clean_text.rfind(". ", start + self.overlap, end)
                    if break_pos != -1:
                        break_pos += 1

                if break_pos != -1 and break_pos > start:
                    end = break_pos

            chunk_str = clean_text[start:end].strip()
            if chunk_str:
                chunks.append(
                    DocumentChunk(
                        text=chunk_str,
                        source_name=source_name,
                        chunk_index=chunk_idx,
                        start_char=start,
                        end_char=end,
                    )
                )
                chunk_idx += 1

            if end >= text_length:
                break

            start = max(start + 1, end - self.overlap)

        return chunks
