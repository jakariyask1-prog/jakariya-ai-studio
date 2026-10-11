"""Registry that resolves independent exporters without conditional chains."""

from __future__ import annotations

from collections.abc import Iterable

from app.export.business_logic.base_exporter import BaseExporter
from app.export.export_options import ExportOptions
from app.export.models import ExportFormatInfo


class UnsupportedExportFormatError(LookupError):
    """Raised when no registered exporter can handle a requested format."""


class ExporterRegistry:
    """Map a format identifier to exactly one exporter implementation."""

    def __init__(self, exporters: Iterable[BaseExporter] = ()) -> None:
        self._exporters: dict[str, BaseExporter] = {}
        for exporter in exporters:
            self.register(exporter)

    def register(self, exporter: BaseExporter) -> None:
        """Register an exporter, rejecting duplicate or incomplete contracts."""
        format_id = ExportOptions.normalize_format_id(exporter.format_id)
        if format_id in self._exporters:
            raise ValueError(f"An exporter for '{format_id}' is already registered.")
        if not getattr(exporter, "file_extension", "").strip():
            raise ValueError(f"Exporter '{format_id}' must define a file extension.")
        self._exporters[format_id] = exporter

    def get(self, format_id: str) -> BaseExporter:
        """Return the exporter for a format or raise a clear lookup error."""
        normalized_format = ExportOptions.normalize_format_id(format_id)
        try:
            return self._exporters[normalized_format]
        except KeyError as error:
            supported = ", ".join(self.supported_format_ids()) or "none"
            raise UnsupportedExportFormatError(
                f"Export format '{normalized_format}' is not supported. Available: {supported}."
            ) from error

    def supported_format_ids(self) -> tuple[str, ...]:
        """Return deterministic format IDs suitable for an export menu."""
        return tuple(sorted(self._exporters))

    def available_formats(self) -> tuple[ExportFormatInfo, ...]:
        """Return UI metadata defined by exporters, not by a hard-coded menu."""
        return tuple(
            ExportFormatInfo(
                format_id=format_id,
                display_name=getattr(exporter, "display_name", format_id.upper()),
                file_extension=exporter.file_extension,
            )
            for format_id, exporter in sorted(self._exporters.items())
        )


def build_default_exporter_registry() -> ExporterRegistry:
    """Compose the initial built-in exporters in one application-level place."""
    from app.export.business_logic.docx_exporter import DocxExporter
    from app.export.business_logic.excel_exporter import ExcelExporter
    from app.export.business_logic.html_exporter import HtmlExporter
    from app.export.business_logic.json_exporter import JsonExporter
    from app.export.business_logic.markdown_exporter import MarkdownExporter
    from app.export.business_logic.pdf_exporter import PdfExporter
    from app.export.business_logic.txt_exporter import TxtExporter

    return ExporterRegistry((JsonExporter(), TxtExporter(), MarkdownExporter(), HtmlExporter(), PdfExporter(), DocxExporter(), ExcelExporter()))


