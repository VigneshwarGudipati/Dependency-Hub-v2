"""Reporting pipeline components."""

from app.services.reporting.report_data import ReportData
from app.services.reporting.report_document import ReportDocument
from app.services.reporting.exporter import ExporterRegistry, UnsupportedFormatError, ReportExportError
from app.services.reporting.exporters.json import JsonExporter
from app.services.reporting.exporters.html import HtmlExporter
from app.services.reporting.exporters.pdf import PdfExporter
from app.services.reporting.filename import generate_safe_filename

# Register exporters explicitly
ExporterRegistry.register(JsonExporter())
ExporterRegistry.register(HtmlExporter())
ExporterRegistry.register(PdfExporter())

__all__ = [
    "ReportData",
    "ReportDocument",
    "ExporterRegistry",
    "UnsupportedFormatError",
    "ReportExportError",
    "generate_safe_filename",
]
