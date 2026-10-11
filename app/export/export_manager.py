"""Stable UI-facing facade for the conversation export system."""

from __future__ import annotations

from pathlib import Path

from app.export.export_options import ExportOptions
from app.export.export_service import ExportService
from app.export.models import ExportFormatInfo, ExportResult


class ExportManager:
    """Expose export actions without coupling UI widgets to export internals."""

    def __init__(self, service: ExportService) -> None:
        self._service = service

    def export_conversation(
        self,
        destination: Path | str,
        options: ExportOptions,
        conversation_id: str | None = None,
    ) -> ExportResult:
        """Export the specified chat, or the currently active chat by default."""
        return self._service.export_conversation(destination, options, conversation_id)

    def available_formats(self) -> tuple[ExportFormatInfo, ...]:
        """Return the formats currently shown by a future export UI."""
        return self._service.available_formats()

    def export_response(self, destination: Path | str, options: ExportOptions, title: str, content: str) -> ExportResult:
        return self._service.export_response(destination, options, title, content)
