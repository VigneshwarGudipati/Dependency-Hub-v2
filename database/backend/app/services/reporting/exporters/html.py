from typing import Any
import markdown
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
        h1, h2, h3 { color: #111; page-break-after: avoid; break-after: avoid; page-break-inside: avoid; break-inside: avoid; }
        .metadata { font-size: 0.9em; color: #666; margin-bottom: 2rem; border-bottom: 1px solid #eee; padding-bottom: 1rem; page-break-inside: avoid; break-inside: avoid; }
        .section { margin-top: 3rem; page-break-inside: auto; break-inside: auto; }
        .metric-cards { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; page-break-inside: auto; break-inside: auto; }
        .card { padding: 1rem; border: 1px solid #ddd; border-radius: 8px; min-width: 150px; page-break-inside: avoid; break-inside: avoid; }
        .card .label { font-size: 0.8em; text-transform: uppercase; color: #666; page-break-after: avoid; break-after: avoid; }
        .card .value { font-size: 1.5em; font-weight: bold; margin-top: 0.5rem; page-break-before: avoid; break-before: avoid; }
        .card.danger { border-color: #ff4d4f; background-color: #fff1f0; }
        .card.success { border-color: #52c41a; background-color: #f6ffed; }
        .card.warning { border-color: #faad14; background-color: #fffbe6; }
        .card.critical { border-color: #cf1322; background-color: #fff1f0; color: #cf1322; }
        .card.high { border-color: #ff4d4f; background-color: #fff1f0; color: #ff4d4f; }
        .card.medium { border-color: #faad14; background-color: #fffbe6; color: #d48806; }
        .card.low { border-color: #d9d9d9; background-color: #fafafa; color: #595959; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.9em; table-layout: fixed; page-break-inside: auto; break-inside: auto; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word; }
        th { background-color: #f8f9fa; font-weight: bold; page-break-inside: avoid; break-inside: avoid; }
        tr { page-break-inside: avoid; break-inside: avoid; page-break-after: auto; break-after: auto; }
        thead { display: table-header-group; }
        ul, ol { padding-left: 20px; }
        li { page-break-inside: avoid; break-inside: avoid; margin-bottom: 0.5rem; }
        code { background-color: #f4f4f4; padding: 2px 4px; border-radius: 4px; font-size: 0.9em; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word; }
        .markdown-content { margin-bottom: 1.5rem; page-break-inside: auto; break-inside: auto; }
        /* Keep section headings with their following content */
        .section > h2 { page-break-after: avoid; break-after: avoid; }
        .section > h2 + .markdown-content,
        .section > h2 + .metric-cards,
        .section > h2 + h3 { page-break-before: avoid; break-before: avoid; }
        @media print {
            body { margin: 0; max-width: none; font-size: 10pt; }
        }
    </style>
</head>
<body>
    <h1>{{ doc.title }}</h1>
    <div class="metadata">
        <p><strong>Project:</strong> {{ doc.project_name }}</p>
        <p><strong>Scan ID:</strong> {{ doc.scan_id }}</p>
        <p><strong>Report ID:</strong> {{ doc.metadata.report_id }}</p>
        <p><strong>Generated At:</strong> {{ doc.metadata.created_at }}</p>
    </div>

    {% for section in doc.sections %}
    <div class="section">
        <h2>{{ section.title }}</h2>
        {% if section.html_content %}
        <div class="markdown-content">{{ section.html_content | safe }}</div>
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
    """Safe HTML exporter utilizing Jinja2 auto-escaping to mitigate XSS and Markdown rendering."""

    def __init__(self):
        # Autoescape is strictly enabled for HTML to escape dynamic untrusted inputs.
        # However, we explicitly mark the markdown output as safe.
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
        # Pre-process markdown content safely. We use python-markdown.
        md = markdown.Markdown(extensions=['tables', 'fenced_code'])
        
        # We need to inject the rendered HTML back into the document context.
        # Since pydantic models might be immutable, we'll convert to dict.
        doc_dict = document.model_dump()
        
        for section in doc_dict['sections']:
            if 'content' in section and section['content']:
                section['html_content'] = md.convert(section['content'])
            else:
                section['html_content'] = ''
        
        html_str = self.template.render(doc=doc_dict)
        return html_str.encode('utf-8')
