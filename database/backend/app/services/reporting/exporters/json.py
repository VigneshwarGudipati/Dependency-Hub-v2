import json
from app.services.reporting.exporter import BaseExporter
from app.services.reporting.report_document import ReportDocument

class JsonExporter(BaseExporter):
    """Deterministic JSON exporter."""

    @property
    def format_id(self) -> str:
        return "json"

    @property
    def content_type(self) -> str:
        return "application/json"

    def export(self, document: ReportDocument) -> bytes:
        # Convert pydantic model to dict, ensuring nested structure
        payload = document.model_dump(mode='json')

        # Deterministic dump: sorted keys, no whitespace in separators, UTF-8
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False
        ).encode('utf-8')
