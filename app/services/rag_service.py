"""RAG (Retrieval-Augmented Generation) & Vector Search Engine."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Tuple, Dict
from app.services.document_chunker import DocumentChunk, DocumentChunker
from app.uploads.file_service import UploadedFile


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric word tokens."""
    return re.findall(r"\w+", text.lower())


class RAGService:
    """In-memory TF-IDF Vector Search Engine for Document Intelligence & Retrieval."""

    def __init__(self, chunk_size: int = 800, overlap: int = 100):
        self.chunker = DocumentChunker(chunk_size=chunk_size, overlap=overlap)

    def search_relevant_chunks(
        self,
        query: str,
        files: List[UploadedFile],
        top_k: int = 4,
    ) -> List[DocumentChunk]:
        """Index uploaded documents and return the top K most relevant text chunks."""
        text_files = [f for f in files if not f.is_image_file and f.text.strip()]
        if not text_files or not query.strip():
            return []

        all_chunks: List[DocumentChunk] = []
        for file in text_files:
            chunks = self.chunker.chunk_document(file.text, file.original_name)
            all_chunks.extend(chunks)

        if not all_chunks:
            return []

        if len(all_chunks) <= top_k:
            return all_chunks

        # Calculate TF-IDF for all chunks
        chunk_tokens = [tokenize(c.text) for c in all_chunks]
        num_chunks = len(all_chunks)

        # Document Frequency
        df: Dict[str, int] = Counter()
        for tokens in chunk_tokens:
            unique_tokens = set(tokens)
            for t in unique_tokens:
                df[t] += 1

        # Inverse Document Frequency
        idf = {word: math.log((1 + num_chunks) / (1 + count)) + 1.0 for word, count in df.items()}

        # Build chunk TF-IDF vectors
        chunk_vectors: List[Dict[str, float]] = []
        for tokens in chunk_tokens:
            tf = Counter(tokens)
            length = len(tokens) or 1
            vector = {word: (count / length) * idf.get(word, 0.0) for word, count in tf.items()}
            chunk_vectors.append(vector)

        # Build query vector
        query_tokens = tokenize(query)
        if not query_tokens:
            return all_chunks[:top_k]

        q_tf = Counter(query_tokens)
        q_len = len(query_tokens)
        q_vector = {word: (count / q_len) * idf.get(word, 0.0) for word, count in q_tf.items()}

        # Compute Cosine Similarity scores
        scores: List[Tuple[float, DocumentChunk]] = []
        q_norm = math.sqrt(sum(val * val for val in q_vector.values())) or 1.0

        for i, chunk in enumerate(all_chunks):
            c_vec = chunk_vectors[i]
            c_norm = math.sqrt(sum(val * val for val in c_vec.values())) or 1.0

            # Dot product
            dot_product = sum(q_vec * c_vec.get(word, 0.0) for word, q_vec in q_vector.items())
            sim = dot_product / (q_norm * c_norm)
            scores.append((sim, chunk))

        # Sort by similarity score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        return [chunk for score, chunk in scores[:top_k]]

    def build_rag_prompt_context(
        self,
        query: str,
        files: List[UploadedFile],
        top_k: int = 4,
    ) -> str:
        """Format relevant document excerpts into structured system context for AI models."""
        relevant_chunks = self.search_relevant_chunks(query, files, top_k=top_k)
        if not relevant_chunks:
            return ""

        sections = [
            f"--- Document Excerpt [{chunk.source_name} | Chunk #{chunk.chunk_index + 1}] ---\n{chunk.text}"
            for chunk in relevant_chunks
        ]

        return (
            "\n\n[DOCUMENT RAG CONTEXT]\n"
            "The user provided relevant document excerpts below. Use these specific excerpts "
            "to answer the query accurately. Cite the source document name when providing factual answers.\n\n"
            + "\n\n".join(sections)
        )
