from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.services.reporting.report_data import ReportData
from app.services.reporting.analyzer.dependency_tree_analyzer import DependencyTreeAnalyzer
from app.services.reporting.analyzer.vulnerability_intelligence_analyzer import VulnerabilityIntelligenceAnalyzer

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
                TableHeader(label="Ecosystem", key="ecosystem"),
                TableHeader(label="Version", key="version"),
                TableHeader(label="Type", key="type"),
                TableHeader(label="Direct", key="is_direct"),
                TableHeader(label="License", key="license"),
                TableHeader(label="Registry State", key="outdated"),
                TableHeader(label="Recommended", key="recommended"),
                TableHeader(label="Upgrade Risk", key="upgrade_risk")
            ],
            rows=[]
        )
        for dep in data.dependencies:
            rec = dep.upgrade_analysis.recommended_version if dep.upgrade_analysis else "N/A"
            risk = dep.upgrade_analysis.upgrade_risk if dep.upgrade_analysis else "N/A"
            dep_table.rows.append(TableRow(cells={
                "id": dep.id,
                "package": dep.package_name,
                "ecosystem": dep.ecosystem,
                "version": dep.package_version,
                "type": dep.dependency_type,
                "is_direct": "Yes" if dep.is_direct else "No",
                "license": dep.registry_metadata.get("license", "UNKNOWN"),
                "outdated": "Outdated" if dep.outdated == "TRUE" else "Up to date" if dep.outdated == "FALSE" else "Unknown",
                "recommended": rec,
                "upgrade_risk": risk
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
                TableHeader(label="Patched Version", key="patched"),
                TableHeader(label="Remediation", key="remediation")
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
                "patched": vuln.patched_version,
                "remediation": vuln.remediation_status or "Open"
            }))

        findings_section = GenericSection(title="Vulnerabilities", content="", tables=[vuln_table])
        doc.sections.append(findings_section)

        # 5.5 Optional Upgrade Analysis & Code Impact Sections
        for dep in data.dependencies:
            if not dep.upgrade_analysis:
                continue
            ua = dep.upgrade_analysis
            content_lines = [f"Dependency: {dep.package_name}"]
            if ua.minimum_fixed_version:
                content_lines.append(f"Minimum fixed version: {ua.minimum_fixed_version}")
            if ua.recommended_version:
                content_lines.append(f"Recommended version: {ua.recommended_version}")
            if ua.latest_known_version:
                content_lines.append(f"Latest known version: {ua.latest_known_version}")
            if ua.manual_review_required:
                content_lines.append("MANUAL REVIEW REQUIRED for this upgrade.")
            if ua.exact_upgrade_command:
                content_lines.append(f"Command: {ua.exact_upgrade_command}")

            ua_metrics = []
            if ua.upgrade_risk:
                ua_metrics.append(MetricCard(label="Upgrade Risk", value=ua.upgrade_risk, severity_class="high" if ua.upgrade_risk in ["HIGH", "CRITICAL"] else "medium" if ua.upgrade_risk == "MEDIUM" else "low"))
            if ua.security_benefit:
                ua_metrics.append(MetricCard(label="Security Benefit", value=ua.security_benefit, severity_class="success"))
            if ua.compatibility_risk:
                ua_metrics.append(MetricCard(label="Compatibility Risk", value=ua.compatibility_risk, severity_class="danger" if ua.compatibility_risk in ["HIGH", "CRITICAL"] else "warning" if ua.compatibility_risk == "MEDIUM" else "success"))

            ua_tables = []

            if ua.breaking_changes:
                bc_table = DataTable(
                    title="Breaking Changes",
                    headers=[TableHeader(label="Category", key="category"), TableHeader(label="Impact", key="impact"), TableHeader(label="Description", key="description")],
                    rows=[TableRow(cells={"category": bc.category, "impact": bc.impact, "description": bc.description}) for bc in ua.breaking_changes]
                )
                ua_tables.append(bc_table)

            if ua.code_impacts:
                ci_table = DataTable(
                    title="Source Code Impact",
                    headers=[TableHeader(label="File", key="file"), TableHeader(label="Line", key="line"), TableHeader(label="Risk", key="risk"), TableHeader(label="Recommendation", key="recommendation")],
                    rows=[TableRow(cells={"file": ci.file_path, "line": str(ci.line_number or ""), "risk": ci.risk, "recommendation": ci.recommendation}) for ci in ua.code_impacts]
                )
                ua_tables.append(ci_table)

            if ua.failure_risks:
                fr_table = DataTable(
                    title="Potential Failure Risks",
                    headers=[TableHeader(label="Scenario", key="scenario"), TableHeader(label="Risk", key="risk"), TableHeader(label="Prevention", key="prevention")],
                    rows=[TableRow(cells={"scenario": fr.scenario, "risk": fr.risk, "prevention": fr.prevention}) for fr in ua.failure_risks]
                )
                ua_tables.append(fr_table)

            ua_section = GenericSection(
                title=f"Upgrade Analysis: {dep.package_name}",
                content="\\n".join(content_lines),
                metrics=ua_metrics,
                tables=ua_tables
            )
            doc.sections.append(ua_section)

        # 5.6 Safe Upgrade Plan Section
        if data.safe_upgrade_plan:
            plan = data.safe_upgrade_plan
            content_lines = ["Follow this safe upgrade procedure:"]
            if plan.before_upgrade:
                content_lines.append("\\nBEFORE UPGRADE:")
                content_lines.extend([f"- {step}" for step in plan.before_upgrade])
            if plan.during_upgrade:
                content_lines.append("\\nDURING UPGRADE:")
                content_lines.extend([f"- {step}" for step in plan.during_upgrade])
            if plan.after_upgrade:
                content_lines.append("\\nAFTER UPGRADE:")
                content_lines.extend([f"- {step}" for step in plan.after_upgrade])

            plan_section = GenericSection(
                title="Safe Upgrade Plan",
                content="\\n".join(content_lines)
            )
            doc.sections.append(plan_section)

        # 6. Dependency Tree Summary Section
        tree_result = DependencyTreeAnalyzer().analyze(data)

        tree_metrics = [
            MetricCard(label="Total Dependencies", value=str(tree_result.total_dependencies)),
            MetricCard(label="Direct", value=str(tree_result.direct_count)),
            MetricCard(label="Non-Direct", value=str(tree_result.non_direct_count)),
            MetricCard(
                label="Cycles Detected",
                value="Yes" if tree_result.cycle_detected else "No",
                severity_class="danger" if tree_result.cycle_detected else "success",
            ),
            MetricCard(
                label="Edge Data Available",
                value="Yes" if tree_result.edges_available else "No",
                severity_class="success" if tree_result.edges_available else "warning",
            ),
        ]

        tree_table = DataTable(
            title="Dependency Relationship Map",
            headers=[
                TableHeader(label="Package", key="package"),
                TableHeader(label="Ecosystem", key="ecosystem"),
                TableHeader(label="Version", key="version"),
                TableHeader(label="Direct", key="direct"),
                TableHeader(label="Parents", key="parents"),
                TableHeader(label="Children", key="children"),
                TableHeader(label="Depth", key="depth"),
            ],
            rows=[
                TableRow(cells={
                    "package": node.package_name,
                    "ecosystem": node.ecosystem,
                    "version": node.package_version,
                    "direct": "Yes" if node.is_direct else "No",
                    "parents": str(len(node.parent_ids)),
                    "children": str(len(node.child_ids)),
                    "depth": str(node.depth) if node.depth >= 0 else "Unknown",
                })
                for node in tree_result.nodes
            ],
        )

        tree_section = GenericSection(
            title="Dependency Tree Summary",
            content=(
                "Relationship structure derived from snapshot edge data. "
                "Depth 0 indicates a direct (root-level) dependency. "
                "Depth -1 / 'Unknown' indicates edge data was unavailable or the node "
                "was unreachable from a known root."
            ),
            metrics=tree_metrics,
            tables=[tree_table],
        )
        doc.sections.append(tree_section)

        # 7. Software Inventory Metadata Section
        schema_version = data.metadata.get("schema_version", "UNKNOWN")
        edge_status = "present" if tree_result.edges_available else "absent"
        sbom_content_lines = [
            f"Snapshot schema version: {schema_version}",
            f"Dependency edge data: {edge_status} in this snapshot.",
            "",
            "VERIFIED AVAILABLE inventory fields:",
            "  package_name, ecosystem, package_version, dependency_type, is_direct,",
            "  license (raw string from registry metadata — not SPDX-validated,",
            "           no legal approval),",
            "  scan_id, project_id, scan_timestamp,",
            "  vulnerability_id, vulnerability_severity.",
            "",
            "AVAILABLE WHEN EDGE DATA PRESENT:",
            "  parent_ids, child_ids, depth, relationship_type.",
            "",
            "NOT AVAILABLE in current snapshot:",
            "  package URL (purl), namespace, group, supplier, author,",
            "  homepage, repository URL, download URL, package checksum/hash,",
            "  source archive hash, copyright text,",
            "  SPDX-validated or legally-verified license expression.",
            "",
            "SBOM generation: No standards-compliant CycloneDX or SPDX SBOM is "
            "generated by this phase. The current snapshot does not contain sufficient "
            "data (purl, hashes, validated license expressions, dependency graph) to "
            "produce a complete CycloneDX 1.4 or SPDX 2.3 document without fabrication. "
            "This section documents the internal software inventory only.",
        ]
        sbom_section = GenericSection(
            title="Software Inventory Metadata",
            content="\n".join(sbom_content_lines),
        )
        doc.sections.append(sbom_section)

        # 8. Detailed Vulnerability Analysis Section
        intelligence_results = VulnerabilityIntelligenceAnalyzer().analyze(data)
        if intelligence_results:
            vuln_rows = []
            for res in intelligence_results:
                vuln_rows.append(
                    TableRow(cells={
                        "vulnerability": f"{res.vulnerability_id} ({res.severity})",
                        "package": f"{res.package_name}@{res.installed_version}",
                        "recommended_fix": res.recommended_version if res.is_fix_available else "UNKNOWN",
                        "compatibility_risk": res.compatibility_risk_summary,
                        "source_impact": res.source_impact_summary,
                        "failure_risk": res.failure_risk_summary,
                        "remediation_status": res.remediation_status,
                    })
                )

            vuln_table = DataTable(
                title="Detailed Findings",
                headers=[
                    TableHeader(label="Vulnerability", key="vulnerability"),
                    TableHeader(label="Package", key="package"),
                    TableHeader(label="Recommended Fix", key="recommended_fix"),
                    TableHeader(label="Compatibility Risk", key="compatibility_risk"),
                    TableHeader(label="Source Impact", key="source_impact"),
                    TableHeader(label="Failure Risk", key="failure_risk"),
                    TableHeader(label="Remediation Status", key="remediation_status"),
                ],
                rows=vuln_rows
            )

            intel_section = GenericSection(
                title="Detailed Vulnerability Analysis",
                content=(
                    "This section synthesizes verified security evidence, fix availability, "
                    "and projected upgrade risks. It maps dependency-level upgrade "
                    "evidence down to the specific vulnerability context. Missing data "
                    "indicates a lack of offline snapshot evidence and is left UNKNOWN "
                    "to prevent fabricated claims."
                ),
                tables=[vuln_table]
            )
            doc.sections.append(intel_section)

        # 9. Limitations / Data Availability
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
