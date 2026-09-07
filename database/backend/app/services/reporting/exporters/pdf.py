import io
import logging
from xhtml2pdf import pisa
from app.services.reporting.exporter import BaseExporter, ReportExportError
from app.services.reporting.report_document import ReportDocument
from app.services.reporting.exporters.html import HtmlExporter

logger = logging.getLogger(__name__)

class PdfRenderError(ReportExportError):
    """Failed to render PDF document."""
    pass

def _sandboxed_link_callback(uri, rel):
    """
    Strictly forbids network or filesystem access during PDF rendering.
    This prevents SSRF and Local File Disclosure vulnerabilities.
    """
    # If the HTML template tries to load any external resource (img, css, fonts),
    # this callback will return None, signaling xhtml2pdf to drop the resource.
    logger.warning(f"PDF sandbox blocked resource access: {uri}")
    return None

class PdfExporter(BaseExporter):
    """Safe PDF exporter utilizing xhtml2pdf with a restricted link callback sandbox."""

    def __init__(self):
        self.html_exporter = HtmlExporter()

    @property
    def format_id(self) -> str:
        return "pdf"

    @property
    def content_type(self) -> str:
        return "application/pdf"

    def export(self, document: ReportDocument) -> bytes:
        # 1. Generate Safe HTML
        html_bytes = self.html_exporter.export(document)

        # 2. Render to PDF
        pdf_out = io.BytesIO()
        pisa_status = pisa.CreatePDF(
            src=html_bytes,
            dest=pdf_out,
            link_callback=_sandboxed_link_callback
        )

        if pisa_status.err:
            raise PdfRenderError("PDF_RENDER_FAILED: Internal xhtml2pdf error.")

        return pdf_out.getvalue()
