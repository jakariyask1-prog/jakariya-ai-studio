"""Unit tests for RAG (Retrieval-Augmented Generation) & Document Vector Search Engine."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.document_chunker import DocumentChunker
from app.services.rag_service import RAGService
from app.uploads.file_service import UploadedFile, FileService


class RAGServiceTests(unittest.TestCase):
    def test_document_chunker_splits_paragraphs_correctly(self):
        chunker = DocumentChunker(chunk_size=100, overlap=20)
        sample_text = (
            "Paragraph one is about software architecture.\n\n"
            "Paragraph two describes Python and PySide6 UI development.\n\n"
            "Paragraph three explains SQLite WAL mode database persistence."
        )
        chunks = chunker.chunk_document(sample_text, "sample.txt")
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0].source_name, "sample.txt")
        self.assertIn("Paragraph", chunks[0].text)

    def test_rag_service_vector_search_relevance_ranking(self):
        rag = RAGService(chunk_size=150, overlap=20)

        file1 = UploadedFile(
            original_name="billing_policy.pdf",
            stored_path=Path("/tmp/billing_policy.pdf"),
            extension=".pdf",
            text=(
                "Section 1: Billing and Invoicing.\n"
                "Invoices are issued on the 1st day of every month.\n"
                "Late payment fee is 5 percent after 15 days grace period."
            ),
        )

        file2 = UploadedFile(
            original_name="hr_policy.pdf",
            stored_path=Path("/tmp/hr_policy.pdf"),
            extension=".pdf",
            text=(
                "Section 2: Employee Leave Policy.\n"
                "Casual leave allowance is 14 days per calendar year.\n"
                "Medical leave requests require doctor certificate after 3 days."
            ),
        )

        results = rag.search_relevant_chunks("What is the late payment fee?", [file1, file2], top_k=2)
        self.assertGreater(len(results), 0)
        top_match = results[0]
        self.assertEqual(top_match.source_name, "billing_policy.pdf")
        self.assertIn("payment", top_match.text.lower())

    def test_rag_prompt_context_generation(self):
        rag = RAGService(chunk_size=200, overlap=30)
        file = UploadedFile(
            original_name="project_spec.docx",
            stored_path=Path("/tmp/project_spec.docx"),
            extension=".docx",
            text="Project Alpha release date is target for December 2026.",
        )
        context = rag.build_rag_prompt_context("When is Project Alpha release?", [file])
        self.assertIn("[DOCUMENT RAG CONTEXT]", context)
        self.assertIn("project_spec.docx", context)
        self.assertIn("Project Alpha release date", context)

    def test_file_service_build_ai_context_triggers_rag_for_large_files(self):
        file_service = FileService()
        large_text = "Software engineering principle and clean architecture patterns. " * 100
        large_file = UploadedFile(
            original_name="large_doc.txt",
            stored_path=Path("/tmp/large_doc.txt"),
            extension=".txt",
            text=large_text,
        )

        context = file_service.build_ai_context([large_file], query="clean architecture")
        self.assertIn("[DOCUMENT RAG CONTEXT]", context)
        self.assertIn("large_doc.txt", context)
