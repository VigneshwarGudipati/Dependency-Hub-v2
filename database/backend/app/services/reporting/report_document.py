from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.services.reporting.report_data import ReportData

class ReportDocumentMetadata(BaseModel):
    document_schema_version: str = "1.0.0"
    generator_version: str
    report_id: str
    snapshot_sha256: str
    created_at: str

class MetricCard(BaseModel):
    label: str
    value: str
    severity_class: Optional[str] = None

class TableHeader(BaseModel):
    label: str
    key: str

class TableRow(BaseModel):
    cells: Dict[str, Any]

class DataTable(BaseModel):
    title: str
    headers: List[TableHeader]
    rows: List[TableRow]

class GenericSection(BaseModel):
    title: str
    content: str
    metrics: List[MetricCard] = Field(default_factory=list)
    tables: List[DataTable] = Field(default_factory=list)

class ReportDocument(BaseModel):
    """
    Presentation-neutral semantics for export formats (JSON, HTML, PDF).
    Translates raw normalized data into universal layout components.
    """
    metadata: ReportDocumentMetadata
    title: str
    project_name: str
    scan_id: str
    sections: List[GenericSection] = Field(default_factory=list)

    @classmethod
    def from_report_data(cls, data: ReportData) -> "ReportDocument":
        """Builds a neutral document explicitly from verified ReportData."""

        # 1. Metadata mapping
        metadata = ReportDocumentMetadata(
            generator_version=data.metadata.get("generator_version", "UNKNOWN"),
            report_id=data.metadata.get("report_id", "UNKNOWN"),
            snapshot_sha256=data.metadata.get("snapshot_sha256", "UNKNOWN"),
            created_at=data.metadata.get("created_at", "UNKNOWN")
        )

        doc = cls(
            metadata=metadata,
            title="Security Dependency Report",
            project_name=data.project.name,
            scan_id=data.scan.id
        )

        # 2. Executive Summary Section
        summary_section = GenericSection(
            title="Executive Summary",
            content="Overview of the open source dependencies and associated vulnerabilities detected during the scan.",
            metrics=[
                MetricCard(label="Total Packages", value=str(data.summary.total_packages)),
                MetricCard(label="Vulnerable Packages", value=str(data.summary.vulnerable_packages), severity_class="danger" if data.summary.vulnerable_packages > 0 else "success"),
                MetricCard(label="Total Findings", value=str(data.summary.vulnerability_findings), severity_class="danger" if data.summary.vulnerability_findings > 0 else "success"),
                MetricCard(label="Outdated Packages", value=str(data.summary.outdated_packages), severity_class="warning"),
                MetricCard(label="Unknown Registry State", value=str(data.summary.unknown_packages)),
            ]
        )
        doc.sections.append(summary_section)

        # 3. Severity Breakdown
        severity_section = GenericSection(
            title="Severity Breakdown",
            content="Vulnerability severity distribution.",
            metrics=[
                MetricCard(label="Critical", value=str(data.summary.severity_counts.CRITICAL), severity_class="critical"),
                MetricCard(label="High", value=str(data.summary.severity_counts.HIGH), severity_class="high"),
                MetricCard(label="Medium", value=str(data.summary.severity_counts.MEDIUM), severity_class="medium"),
                MetricCard(label="Low", value=str(data.summary.severity_counts.LOW), severity_class="low"),
            ]
        )
        doc.sections.append(severity_section)

        # 4. Dependency Inventory Table
        dep_table = DataTable(
            title="Dependency Inventory",
            headers=[
                TableHeader(label="Package", key="package"),
                TableHeader(label="Version", key="version"),
                TableHeader(label="Type", key="type"),
                TableHeader(label="Registry State", key="outdated")
            ],
            rows=[]
        )
        for dep in data.dependencies:
            dep_table.rows.append(TableRow(cells={
                "id": dep.id,
                "package": dep.package_name,
                "version": dep.package_version,
                "type": dep.dependency_type,
                "outdated": "Outdated" if dep.outdated == "TRUE" else "Up to date" if dep.outdated == "FALSE" else "Unknown"
            }))

        inventory_section = GenericSection(title="Dependencies", content="", tables=[dep_table])
        doc.sections.append(inventory_section)

        # 5. Vulnerability Findings Table
        vuln_table = DataTable(
            title="Vulnerability Findings",
            headers=[
                TableHeader(label="Advisory", key="advisory"),
                TableHeader(label="Severity", key="severity"),
                TableHeader(label="Package", key="package"),
                TableHeader(label="Patched Version", key="patched")
            ],
            rows=[]
        )

        # Fast lookup for dependency names
        dep_map = {dep.id: dep.package_name for dep in data.dependencies}

        for vuln in data.vulnerabilities:
            pkg_name = dep_map.get(vuln.dependency_id, "UNKNOWN")
            vuln_table.rows.append(TableRow(cells={
                "advisory": vuln.vulnerability_id,
                "severity": vuln.severity,
                "package": pkg_name,
                "patched": vuln.patched_version
            }))

        findings_section = GenericSection(title="Vulnerabilities", content="", tables=[vuln_table])
        doc.sections.append(findings_section)

        # 6. Limitations / Data Availability
        limitations = []
        if data.summary.unknown_packages > 0:
            limitations.append(f"{data.summary.unknown_packages} packages have an unknown registry status.")

        limitations_content = " ".join(limitations) if limitations else "No significant limitations detected."

        limitations_section = GenericSection(
            title="Data Availability & Limitations",
            content=limitations_content
        )
        doc.sections.append(limitations_section)

        return doc
