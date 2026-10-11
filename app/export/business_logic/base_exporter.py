"""Common contract implemented by each conversation export format."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.export.export_options import ExportOptions
from app.export.models import ExportConversation


class BaseExporter(ABC):
    """Write one :class:`ExportConversation` in one output format."""

    format_id: str
    display_name: str
    file_extension: str

    @abstractmethod
    def export(
        self,
        conversation: ExportConversation,
        destination: Path,
        options: ExportOptions,
    ) -> Path:
        """Write the export and return its final path.

        Implementations own their rendering details.  They must raise a
        descriptive exception when their format cannot be written.
        """
