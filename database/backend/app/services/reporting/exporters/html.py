from typing import Any
from jinja2 import Environment, BaseLoader, select_autoescape
from app.services.reporting.exporter import BaseExporter
from app.services.reporting.report_document import ReportDocument

# Standalone HTML template ensuring safe CSS and complete offline readability.
# We apply a strict CSP meta tag since this is standalone HTML.
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:">
    <title>{{ doc.title }} - {{ doc.project_name }}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; margin: 40px auto; max-width: 1200px; padding: 0 20px; }
        h1, h2, h3 { color: #111; }
        .metadata { font-size: 0.9em; color: #666; margin-bottom: 2rem; border-bottom: 1px solid #eee; padding-bottom: 1rem; }
        .section { margin-top: 3rem; }
        .metric-cards { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }
        .card { padding: 1rem; border: 1px solid #ddd; border-radius: 8px; min-width: 150px; }
        .card .label { font-size: 0.8em; text-transform: uppercase; color: #666; }
        .card .value { font-size: 1.5em; font-weight: bold; margin-top: 0.5rem; }
        .card.danger { border-color: #ff4d4f; background-color: #fff1f0; }
        .card.success { border-color: #52c41a; background-color: #f6ffed; }
        .card.warning { border-color: #faad14; background-color: #fffbe6; }
        .card.critical { border-color: #cf1322; background-color: #fff1f0; color: #cf1322; }
        .card.high { border-color: #ff4d4f; background-color: #fff1f0; color: #ff4d4f; }
        .card.medium { border-color: #faad14; background-color: #fffbe6; color: #d48806; }
        .card.low { border-color: #d9d9d9; background-color: #fafafa; color: #595959; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.9em; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; font-weight: bold; }
        @media print {
            body { margin: 0; max-width: none; }
            .section { page-break-inside: avoid; }
            table { page-break-inside: auto; }
            tr { page-break-inside: avoid; page-break-after: auto; }
            thead { display: table-header-group; }
        }
    </style>
</head>
<body>
    <h1>{{ doc.title }}</h1>
    <div class="metadata">
        <p><strong>Project:</strong> {{ doc.project_name }}</p>
        <p><strong>Scan ID:</strong> {{ doc.scan_id }}</p>
        <p><strong>Generated At:</strong> {{ doc.metadata.created_at }}</p>
        <p><strong>Report ID:</strong> {{ doc.metadata.report_id }}</p>
    </div>

    {% for section in doc.sections %}
    <div class="section">
        <h2>{{ section.title }}</h2>
        {% if section.content %}
        <p>{{ section.content }}</p>
        {% endif %}

        {% if section.metrics %}
        <div class="metric-cards">
            {% for metric in section.metrics %}
            <div class="card {% if metric.severity_class %}{{ metric.severity_class }}{% endif %}">
                <div class="label">{{ metric.label }}</div>
                <div class="value">{{ metric.value }}</div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% for table in section.tables %}
        <h3>{{ table.title }}</h3>
        <table>
            <thead>
                <tr>
                    {% for header in table.headers %}
                    <th>{{ header.label }}</th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for row in table.rows %}
                <tr>
                    {% for header in table.headers %}
                    <td>{{ row.cells[header.key] }}</td>
                    {% endfor %}
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endfor %}
    </div>
    {% endfor %}
</body>
</html>"""

class HtmlExporter(BaseExporter):
    """Safe HTML exporter utilizing Jinja2 auto-escaping to mitigate XSS."""

    def __init__(self):
        # Autoescape is strictly enabled for HTML to escape dynamic untrusted inputs.
        self.env = Environment(
            loader=BaseLoader(),
            autoescape=select_autoescape(['html', 'xml'])
        )
        self.template = self.env.from_string(HTML_TEMPLATE)

    @property
    def format_id(self) -> str:
        return "html"

    @property
    def content_type(self) -> str:
        return "text/html"

    def export(self, document: ReportDocument) -> bytes:
        html_str = self.template.render(doc=document)
        return html_str.encode('utf-8')
