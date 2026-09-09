from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.services.reporting.report_data import ReportData
from app.services.reporting.analyzer.dependency_tree_analyzer import DependencyTreeAnalyzer
from app.services.reporting.analyzer.vulnerability_intelligence_analyzer import VulnerabilityIntelligenceAnalyzer
from app.services.reporting.analyzer.upgrade_validation_analyzer import UpgradeValidationAnalyzer

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
            document_schema_version=data.metadata.get("schema_version", "1.0.0"),
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

        # 1. Report Cover
        cover_section = GenericSection(
            title="1. Report Cover",
            content=(
                f"**Report Title:** Security Dependency Report\n\n"
                f"**Project:** {data.project.name}\n\n"
                f"**Scan ID:** {data.scan.id}\n\n"
                f"**Report ID:** {metadata.report_id}\n\n"
                f"**Generated At:** {metadata.created_at}\n\n"
            )
        )
        doc.sections.append(cover_section)

        # Pre-compute metrics
        manual_reviews = 0
        fixes_available = set()
        high_compatibility_risks = 0
        high_failure_risks = 0

        for dep in data.dependencies:
            if dep.upgrade_analysis:
                if dep.upgrade_analysis.manual_review_required or not dep.upgrade_analysis.exact_upgrade_command:
                    manual_reviews += 1
                if dep.upgrade_analysis.resolved_vulnerabilities:
                    for v_id in dep.upgrade_analysis.resolved_vulnerabilities:
                        fixes_available.add(v_id)
                if dep.upgrade_analysis.compatibility_risk in ("HIGH", "CRITICAL"):
                    high_compatibility_risks += 1
                if any(fr.risk in ("HIGH", "CRITICAL") for fr in dep.upgrade_analysis.failure_risks):
                    high_failure_risks += 1

        remediated_count = sum(1 for v in data.vulnerabilities if v.remediation_status == "VERIFIED REMEDIATED")
        still_present_count = sum(1 for v in data.vulnerabilities if v.remediation_status == "VERIFIED STILL PRESENT")

        # 2. Executive Summary
        summary_section = GenericSection(
            title="2. Executive Summary",
            content=(
                "### FACTS\n"
                "Overview of the open source dependencies and associated vulnerabilities detected during the scan. "
                "Metrics below are derived directly from the verified snapshot.\n\n"
                "### RECOMMENDATIONS\n"
                "Review the Final Recommendation section for detailed next steps based on these facts."
            ),
            metrics=[
                MetricCard(label="Total Packages", value=str(data.summary.total_packages)),
                MetricCard(label="Vulnerable Packages", value=str(data.summary.vulnerable_packages), severity_class="danger" if data.summary.vulnerable_packages > 0 else "success"),
                MetricCard(label="Total Findings", value=str(data.summary.vulnerability_findings), severity_class="danger" if data.summary.vulnerability_findings > 0 else "success"),
                MetricCard(label="Outdated Packages", value=str(data.summary.outdated_packages), severity_class="warning" if data.summary.outdated_packages > 0 else "success"),
                MetricCard(label="Unknown Registry State", value=str(data.summary.unknown_packages)),
                MetricCard(label="Fix Evidence Available", value=str(len(fixes_available)), severity_class="success"),
            ]
        )
        doc.sections.append(summary_section)

        # 3. Severity Breakdown
        severity_section = GenericSection(
            title="3. Severity Breakdown",
            content=(
                "Vulnerability severity distribution based on verified vulnerability findings. "
                "A severity count of 0 indicates no verified findings for that severity class in this snapshot."
            ),
            metrics=[
                MetricCard(label="Critical", value=str(data.summary.severity_counts.CRITICAL), severity_class="critical" if data.summary.severity_counts.CRITICAL > 0 else "success"),
                MetricCard(label="High", value=str(data.summary.severity_counts.HIGH), severity_class="high" if data.summary.severity_counts.HIGH > 0 else "success"),
                MetricCard(label="Medium", value=str(data.summary.severity_counts.MEDIUM), severity_class="medium" if data.summary.severity_counts.MEDIUM > 0 else "success"),
                MetricCard(label="Low", value=str(data.summary.severity_counts.LOW), severity_class="low" if data.summary.severity_counts.LOW > 0 else "success"),
            ]
        )
        doc.sections.append(severity_section)

        # 4. Dependency Inventory
        dep_table = DataTable(
            title="Dependency Inventory",
            headers=[
                TableHeader(label="Package", key="package"),
                TableHeader(label="Ecosystem", key="ecosystem"),
                TableHeader(label="Version", key="version"),
                TableHeader(label="Type", key="type"),
                TableHeader(label="Source", key="is_direct"),
                TableHeader(label="License", key="license"),
                TableHeader(label="Registry Status", key="outdated"),
                TableHeader(label="Vuln Count", key="vuln_count"),
                TableHeader(label="Evidence Status", key="evidence_status")
            ],
            rows=[]
        )
        
        # Calculate vulns per dependency
        vuln_counts = {}
        for vuln in data.vulnerabilities:
            vuln_counts[vuln.dependency_id] = vuln_counts.get(vuln.dependency_id, 0) + 1

        for dep in data.dependencies:
            evidence_status = "VERIFIED" if dep.registry_metadata and dep.registry_metadata.get("outdated") is not None else "UNKNOWN"
            dep_table.rows.append(TableRow(cells={
                "package": dep.package_name,
                "ecosystem": dep.ecosystem,
                "version": dep.package_version,
                "type": dep.dependency_type,
                "is_direct": "Direct" if dep.is_direct else "Transitive",
                "license": dep.registry_metadata.get("license", "UNKNOWN") if dep.registry_metadata else "UNKNOWN",
                "outdated": "Outdated" if dep.outdated == "TRUE" else "Up to date" if dep.outdated == "FALSE" else "UNKNOWN",
                "vuln_count": str(vuln_counts.get(dep.id, 0)),
                "evidence_status": evidence_status
            }))

        if not data.dependencies:
            inventory_section = GenericSection(title="4. Dependency Inventory", content="No verified dependencies were identified in this snapshot.")
        else:
            inventory_section = GenericSection(title="4. Dependency Inventory", content="Complete list of acquired dependencies.", tables=[dep_table])
        doc.sections.append(inventory_section)

        # 5. Dependency Tree Summary
        tree_result = DependencyTreeAnalyzer().analyze(data)
        tree_metrics = [
            MetricCard(label="Total Dependencies", value=str(tree_result.total_dependencies)),
            MetricCard(label="Direct", value=str(tree_result.direct_count)),
            MetricCard(label="Non-Direct", value=str(tree_result.non_direct_count)),
            MetricCard(label="Cycles Detected", value="Yes" if tree_result.cycle_detected else "No", severity_class="danger" if tree_result.cycle_detected else "success"),
        ]

        if not tree_result.edges_available:
            tree_section = GenericSection(
                title="5. Dependency Tree Summary",
                content="No dependency graph edge data (parent/child relationships) is available in this snapshot. Only flat dependency inventory is known.",
                metrics=tree_metrics
            )
        else:
            tree_table = DataTable(
                title="Dependency Relationship Map",
                headers=[
                    TableHeader(label="Package", key="package"),
                    TableHeader(label="Version", key="version"),
                    TableHeader(label="Direct", key="direct"),
                    TableHeader(label="Parents", key="parents"),
                    TableHeader(label="Children", key="children"),
                    TableHeader(label="Depth", key="depth"),
                ],
                rows=[
                    TableRow(cells={
                        "package": node.package_name,
                        "version": node.package_version,
                        "direct": "Yes" if node.is_direct else "No",
                        "parents": str(len(node.parent_ids)),
                        "children": str(len(node.child_ids)),
                        "depth": str(node.depth) if node.depth >= 0 else "UNKNOWN",
                    })
                    for node in tree_result.nodes
                ],
            )
            tree_section = GenericSection(title="5. Dependency Tree Summary", content="Relationship structure derived from snapshot edge data.", metrics=tree_metrics, tables=[tree_table])
        doc.sections.append(tree_section)

        # 6. Software Inventory Metadata
        schema_version = data.metadata.get("schema_version", "UNKNOWN")
        sbom_content_lines = [
            f"**Snapshot schema version:** {schema_version}\n",
            "**VERIFIED AVAILABLE inventory fields:**",
            "- `package_name`, `ecosystem`, `package_version`, `dependency_type`, `is_direct`",
            "- `license` (raw string from registry metadata — not SPDX-validated)",
            "- `vulnerability_id`, `vulnerability_severity`\n",
            "**NOT AVAILABLE in current snapshot:**",
            "- `purl`, package checksum/hash, exact source-code usage.",
            "- SPDX-validated or legally-verified license expressions.\n",
            "**SBOM status:** No standards-compliant CycloneDX or SPDX SBOM is generated by this phase due to missing cryptographic hashing and namespace data in the raw scanner acquisition."
        ]
        doc.sections.append(GenericSection(title="6. Software Inventory Metadata", content="\n".join(sbom_content_lines)))

        # 7. Vulnerability Findings
        if not data.vulnerabilities:
            findings_section = GenericSection(title="7. Vulnerability Findings", content="No verified vulnerability findings were identified in this snapshot.")
        else:
            vuln_table = DataTable(
                title="Vulnerability Findings",
                headers=[
                    TableHeader(label="Package", key="package"),
                    TableHeader(label="Version", key="version"),
                    TableHeader(label="Identifier", key="advisory"),
                    TableHeader(label="Severity", key="severity"),
                    TableHeader(label="Patched Version", key="patched"),
                    TableHeader(label="Evidence Status", key="evidence")
                ],
                rows=[]
            )
            dep_map = {dep.id: dep for dep in data.dependencies}
            for vuln in data.vulnerabilities:
                pkg = dep_map.get(vuln.dependency_id)
                pkg_name = pkg.package_name if pkg else "UNKNOWN"
                pkg_ver = pkg.package_version if pkg else "UNKNOWN"
                vuln_table.rows.append(TableRow(cells={
                    "package": pkg_name,
                    "version": pkg_ver,
                    "advisory": vuln.vulnerability_id,
                    "severity": vuln.severity,
                    "patched": vuln.patched_version or "UNKNOWN — not verified",
                    "evidence": "VERIFIED"
                }))
            findings_section = GenericSection(title="7. Vulnerability Findings", content="All explicitly discovered vulnerabilities tracked to dependencies in this snapshot.", tables=[vuln_table])
        doc.sections.append(findings_section)

        # 8. Detailed Vulnerability Analysis
        intelligence_results = VulnerabilityIntelligenceAnalyzer().analyze(data)
        if not intelligence_results:
            intel_section = GenericSection(title="8. Detailed Vulnerability Analysis", content="No detailed vulnerability evidence is available in this snapshot.")
        else:
            vuln_rows = []
            for res in intelligence_results:
                vuln_rows.append(
                    TableRow(cells={
                        "vulnerability": f"{res.vulnerability_id}",
                        "package": f"{res.package_name}@{res.installed_version}",
                        "impact": "POTENTIAL",
                        "status": "VERIFIED" if res.is_fix_available else "MANUAL REVIEW REQUIRED",
                        "recommended_fix": res.recommended_version if res.is_fix_available else "UNKNOWN"
                    })
                )
            vuln_intel_table = DataTable(
                title="Detailed Findings",
                headers=[
                    TableHeader(label="Vulnerability", key="vulnerability"),
                    TableHeader(label="Package", key="package"),
                    TableHeader(label="Exploitability Impact", key="impact"),
                    TableHeader(label="Evidence Status", key="status"),
                    TableHeader(label="Recommended Fix", key="recommended_fix"),
                ],
                rows=vuln_rows
            )
            intel_section = GenericSection(title="8. Detailed Vulnerability Analysis", content="Detailed breakdown of fixes and exploitability based strictly on available offline metadata.", tables=[vuln_intel_table])
        doc.sections.append(intel_section)

        # 9. Upgrade Analysis
        ua_content_lines = []
        ua_tables = []
        has_upgrade_analysis = False

        for dep in data.dependencies:
            if not dep.upgrade_analysis:
                continue
            has_upgrade_analysis = True
            ua = dep.upgrade_analysis
            ua_content_lines.append(f"### {dep.package_name}")
            ua_content_lines.append(f"- **Current Version:** {dep.package_version}")
            ua_content_lines.append(f"- **Target Version:** {ua.recommended_version or 'UNKNOWN'}")
            ua_content_lines.append(f"- **Risk Profile:** {ua.upgrade_risk or 'UNKNOWN'}")
            if ua.manual_review_required:
                ua_content_lines.append("- **Status:** MANUAL REVIEW REQUIRED.")
            ua_content_lines.append("")

            if ua.breaking_changes:
                bc_table = DataTable(
                    title=f"Breaking Changes: {dep.package_name}",
                    headers=[TableHeader(label="Category", key="category"), TableHeader(label="Impact", key="impact"), TableHeader(label="Description", key="description")],
                    rows=[TableRow(cells={"category": bc.category, "impact": bc.impact, "description": bc.description}) for bc in ua.breaking_changes]
                )
                ua_tables.append(bc_table)

        if has_upgrade_analysis:
            ua_section = GenericSection(title="9. Upgrade Analysis", content="\n".join(ua_content_lines), tables=ua_tables)
        else:
            ua_section = GenericSection(title="9. Upgrade Analysis", content="No verified upgrade recommendation is available from the current evidence.")
        doc.sections.append(ua_section)

        # 10. Safe Upgrade Plan
        if data.safe_upgrade_plan:
            plan = data.safe_upgrade_plan
            content_lines = []
            if plan.before_upgrade:
                content_lines.append("### Pre-Check & Backup")
                content_lines.extend([f"- {step} (RECOMMENDED)" for step in plan.before_upgrade])
            if plan.during_upgrade:
                content_lines.append("\n### Upgrade Order")
                content_lines.extend([f"- {step} (VERIFIED)" for step in plan.during_upgrade])
            if plan.after_upgrade:
                content_lines.append("\n### Test Execution & Validation")
                content_lines.extend([f"- {step} (RECOMMENDED)" for step in plan.after_upgrade])

            plan_section = GenericSection(title="10. Safe Upgrade Plan", content="\n".join(content_lines))
        else:
            plan_section = GenericSection(title="10. Safe Upgrade Plan", content="No verified safe upgrade plan is available.")
        doc.sections.append(plan_section)

        validation_results = UpgradeValidationAnalyzer().analyze(data)

        # 11. Pre-Upgrade Checklist
        if validation_results:
            checklist_content = []
            for res in validation_results:
                checklist_content.append(f"### {res.package_name}")
                for item in res.pre_upgrade_checklist:
                    checklist_content.append(f"- [ ] {item}")
                checklist_content.append("")
            pre_upgrade_section = GenericSection(title="11. Pre-Upgrade Checklist", content="\n".join(checklist_content))
        else:
            pre_upgrade_section = GenericSection(title="11. Pre-Upgrade Checklist", content="No verified checklist available. MANUAL REVIEW REQUIRED.")
        doc.sections.append(pre_upgrade_section)

        # 12. Upgrade & Rollback Plan
        if validation_results:
            rollback_content = []
            for res in validation_results:
                rollback_content.append(f"### {res.package_name}")
                rollback_content.append("**Rollback Prerequisite / Trigger:**")
                rollback_content.append("- Ensure lockfile is backed up prior to execution.")
                rollback_content.append("\n**Rollback Procedure:**")
                for step in res.rollback_plan.procedural_steps:
                    rollback_content.append(f"- {step}")
                rollback_content.append("\n**Rollback Validation:**")
                for step in res.rollback_plan.verification_steps:
                    rollback_content.append(f"- {step}")
                rollback_content.append("")
            rollback_section = GenericSection(title="12. Upgrade & Rollback Plan", content="\n".join(rollback_content))
        else:
            rollback_section = GenericSection(title="12. Upgrade & Rollback Plan", content="No verified rollback plan available.")
        doc.sections.append(rollback_section)

        # 13. Post-Upgrade Validation Matrix
        if validation_results:
            matrix_tables = []
            for res in validation_results:
                matrix_rows = []
                for val in res.validations:
                    matrix_rows.append(TableRow(cells={
                        "validation": val.category, "expected_result": val.expected_result,
                        "status": val.status, "evidence": val.evidence_source
                    }))
                matrix_table = DataTable(
                    title=f"Validation Matrix: {res.package_name}",
                    headers=[
                        TableHeader(label="Validation", key="validation"),
                        TableHeader(label="Expected Result", key="expected_result"),
                        TableHeader(label="Status", key="status"),
                        TableHeader(label="Evidence", key="evidence")
                    ],
                    rows=matrix_rows
                )
                matrix_tables.append(matrix_table)
            matrix_section = GenericSection(title="13. Post-Upgrade Validation Matrix", content="Post-upgrade application health validations.", tables=matrix_tables)
        else:
            matrix_section = GenericSection(title="13. Post-Upgrade Validation Matrix", content="No post-upgrade validations defined. MANUAL REVIEW REQUIRED.")
        doc.sections.append(matrix_section)

        # 14. Methodology & Data Sources
        methodology_content = [
            f"- **Snapshot Identity:** {metadata.snapshot_sha256}",
            f"- **Repository Provenance:** Scan ID `{data.scan.id}` / Project ID `{data.project.id}`",
            f"- **Analyzer Version:** {metadata.generator_version}",
            f"- **Generation Timestamp:** {metadata.created_at}",
            "\n**Constraints:** Read-only analysis of frozen snapshot data. No live provider requests execute during PDF/HTML formatting. Exact source-code usage inside functions is NOT dynamically traced."
        ]
        doc.sections.append(GenericSection(title="14. Methodology & Data Sources", content="\n".join(methodology_content)))

        # 15. Limitations
        limitations = []
        if data.summary.unknown_packages > 0:
            limitations.append(f"- **Registry metadata unavailable:** {data.summary.unknown_packages} packages lack version tracking.")
        if not tree_result.edges_available:
            limitations.append("- **Dependency Graph:** Transitive upgrade compatibility not verified (missing edge data).")
        if manual_reviews > 0:
            limitations.append(f"- **Manual Review:** {manual_reviews} components require human inspection before upgrade.")
            
        if not limitations:
            limitations.append("- No specific evidence gaps identified for this snapshot.")

        doc.sections.append(GenericSection(title="15. Limitations", content="\n".join(limitations)))

        # 16. Final Recommendation
        recommendation_parts = []
        if high_compatibility_risks > 0 or high_failure_risks > 0:
            recommendation_parts.append("**MANUAL SECURITY REVIEW REQUIRED.** High compatibility risks detected. Do not fully automate upgrades.")
        elif manual_reviews > 0:
            recommendation_parts.append("**INSUFFICIENT EVIDENCE FOR SAFE RECOMMENDATION.** Automated upgrade paths are missing or require human validation.")
        elif len(fixes_available) > 0:
            recommendation_parts.append("**VERIFIED UPGRADE RECOMMENDED.** Clear upgrade paths exist for identified vulnerabilities. Proceed with Safe Upgrade Plan.")
        elif still_present_count > 0:
            recommendation_parts.append("**MANUAL SECURITY REVIEW REQUIRED.** Verified still-present vulnerabilities without clean fixes detected.")
        else:
            recommendation_parts.append("**NO VERIFIED ACTION REQUIRED.** No actionable security vulnerabilities identified.")

        doc.sections.append(GenericSection(title="16. Final Recommendation", content="\n\n".join(recommendation_parts)))

        return doc
