import abc
import logging
from typing import Dict, Type
from app.services.reporting.report_document import ReportDocument

logger = logging.getLogger(__name__)

class ReportExportError(Exception):
    """Base error for exporter failures."""
    pass

class UnsupportedFormatError(ReportExportError):
    """Requested format is not supported."""
    pass


class BaseExporter(abc.ABC):
    """Abstract base class for all report exporters."""

    @property
    @abc.abstractmethod
    def format_id(self) -> str:
        """The identifier for this format (e.g. 'json', 'pdf')."""
        pass

    @property
    @abc.abstractmethod
    def content_type(self) -> str:
        """The MIME type of the output."""
        pass

    @abc.abstractmethod
    def export(self, document: ReportDocument) -> bytes:
        """Transforms a ReportDocument into raw export bytes."""
        pass


class ExporterRegistry:
    """Explicit static dispatch for exporters to avoid dynamic imports."""

    _exporters: Dict[str, BaseExporter] = {}

    @classmethod
    def register(cls, exporter: BaseExporter):
        cls._exporters[exporter.format_id.lower()] = exporter

    @classmethod
    def get_exporter(cls, format_id: str) -> BaseExporter:
        exporter = cls._exporters.get(format_id.lower())
        if not exporter:
            raise UnsupportedFormatError(f"UNSUPPORTED_FORMAT: {format_id}")
        return exporter
