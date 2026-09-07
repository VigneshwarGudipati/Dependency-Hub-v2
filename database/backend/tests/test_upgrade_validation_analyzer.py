"""
Tests for Phase L: UpgradeValidationAnalyzer
"""
import pytest
import json

from app.services.reporting.report_data import (
    ReportData,
    ReportProjectData,
    ReportScanData,
    ReportSummaryData,
    ReportSeverityCounts,
    ReportDependencyData,
    ReportVulnerabilityData,
    DependencyUpgradeAnalysis,
)
from app.services.reporting.analyzer.upgrade_validation_analyzer import (
    UpgradeValidationAnalyzer,
    UpgradeValidationResult,
)
from app.services.reporting.report_document import ReportDocument
from app.services.reporting.exporters.json import JsonExporter
from app.services.reporting.exporters.html import HtmlExporter
from app.services.reporting.exporters.pdf import PdfExporter

def _dep(
    dep_id="dep-1",
    package_name="test-package",
    ecosystem="npm",
    package_version="1.0.0",
    upgrade_analysis=None
) -> ReportDependencyData:
    return ReportDependencyData(
        id=dep_id,
        package_name=package_name,
        ecosystem=ecosystem,
        package_version=package_version,
        dependency_type="RUNTIME",
        is_direct=True,
        registry_metadata={},
        upgrade_analysis=upgrade_analysis,
    )

def _vuln(
    vuln_id="CVE-2023-1234",
    dep_id="dep-1",
    severity="HIGH",
    remediation_status="UNKNOWN"
) -> ReportVulnerabilityData:
    return ReportVulnerabilityData(
        dependency_id=dep_id,
        vulnerability_id=vuln_id,
        title="Test Vuln",
        severity=severity,
        remediation_status=remediation_status,
    )

def _report(dependencies=None, vulnerabilities=None) -> ReportData:
    return ReportData(
        metadata={
            "project_id": "test",
            "scan_id": "scan",
            "schema_version": "1.1.0",
        },
        project=ReportProjectData(id="p-1", name="Project"),
        scan=ReportScanData(id="s-1", scan_type="FULL", scanner_version="1.0", started_at=None, completed_at=None),
        summary=ReportSummaryData(
            total_packages=len(dependencies or []),
            vulnerable_packages=len(set(v.dependency_id for v in (vulnerabilities or []))),
            vulnerability_findings=len(vulnerabilities or []),
            severity_counts=ReportSeverityCounts()
        ),
        dependencies=dependencies or [],
        vulnerabilities=vulnerabilities or [],
    )

@pytest.fixture
def analyzer() -> UpgradeValidationAnalyzer:
    return UpgradeValidationAnalyzer()

def test_pre_upgrade_checklist(analyzer):
    """1. pre-upgrade checklist generated"""
    ua = DependencyUpgradeAnalysis(recommended_version="1.0.1", exact_upgrade_command="npm i")
    dep = _dep(upgrade_analysis=ua)
    res = analyzer.analyze(_report([dep]))[0]

    assert "Confirm current package version is 1.0.0" in res.pre_upgrade_checklist
    assert "Confirm recommended target version is 1.0.1" in res.pre_upgrade_checklist
    assert "Back up/commit current state (PROCEDURAL GUIDANCE)" in res.pre_upgrade_checklist

def test_version_preservation(analyzer):
    """2. current version preservation, 3. target version preservation, 4. exact command reused verbatim"""
    ua = DependencyUpgradeAnalysis(recommended_version="1.0.1", exact_upgrade_command="npm update pkg --save")
    dep = _dep(upgrade_analysis=ua)
    res = analyzer.analyze(_report([dep]))[0]

    assert res.current_version == "1.0.0"
    assert res.target_version == "1.0.1"
    assert res.exact_upgrade_command == "npm update pkg --save"

def test_validation_matrix_defaults(analyzer):
    """5. validation matrix, 6. unexecuted validations = NOT VERIFIED, 7. no fabricated PASS, 8. manual validation status"""
    ua = DependencyUpgradeAnalysis(recommended_version="1.0.1")
    dep = _dep(upgrade_analysis=ua)
    res = analyzer.analyze(_report([dep]))[0]

    assert len(res.validations) == 10
    for v in res.validations:
        if v.category != "Security rescan":
            assert v.status == "NOT VERIFIED"
            assert v.manual_action_required is True
            assert "PASS" not in v.status
        else:
            assert v.status == "NO FOLLOW-UP SCAN"

def test_rollback_guidance(analyzer):
    """9. rollback references current version, 10. restored version, 11. no infrastructure commands"""
    ua = DependencyUpgradeAnalysis(recommended_version="1.0.1")
    dep = _dep(upgrade_analysis=ua)
    res = analyzer.analyze(_report([dep]))[0]

    assert res.rollback_plan.restored_version == "1.0.0"
    assert any("exact version 1.0.0" in step for step in res.rollback_plan.procedural_steps)
    assert any("resolves exactly to 1.0.0" in step for step in res.rollback_plan.verification_steps)

    # Assert no infrastructure commands
    for step in res.rollback_plan.procedural_steps + res.rollback_plan.verification_steps + res.rollback_plan.limitations:
        assert "docker" not in step.lower()
        assert "kubernetes" not in step.lower()
        assert "kubectl" not in step.lower()

def test_phase_h_integration(analyzer):
    """12. no follow-up scan, 13. VERIFIED REMEDIATED, 14. VERIFIED STILL PRESENT, 15. PARTIALLY REMEDIATED"""
    ua = DependencyUpgradeAnalysis(recommended_version="1.0.1")

    dep1 = _dep(dep_id="d1", upgrade_analysis=ua)
    dep2 = _dep(dep_id="d2", upgrade_analysis=ua)
    dep3 = _dep(dep_id="d3", upgrade_analysis=ua)
    dep4 = _dep(dep_id="d4", upgrade_analysis=ua)

    v1 = _vuln(dep_id="d1", remediation_status="NO FOLLOW-UP SCAN")
    v2 = _vuln(dep_id="d2", remediation_status="VERIFIED REMEDIATED")
    v3 = _vuln(dep_id="d3", remediation_status="VERIFIED STILL PRESENT")
    v4 = _vuln(dep_id="d4", remediation_status="PARTIALLY REMEDIATED")

    res = analyzer.analyze(_report([dep1, dep2, dep3, dep4], [v1, v2, v3, v4]))

    def get_sec_status(d_id):
        return next(
            v.status for r in res if r.dependency_id == d_id for v in r.validations if v.category == "Security rescan"
        )

    assert get_sec_status("d1") == "NO FOLLOW-UP SCAN"
    assert get_sec_status("d2") == "VERIFIED REMEDIATED"
    assert get_sec_status("d3") == "VERIFIED STILL PRESENT"
    assert get_sec_status("d4") == "PARTIALLY REMEDIATED"

def test_deterministic_ordering(analyzer):
    """16. deterministic ordering"""
    ua = DependencyUpgradeAnalysis()
    dep1 = _dep(dep_id="d2", upgrade_analysis=ua)
    dep2 = _dep(dep_id="d1", upgrade_analysis=ua)

    res = analyzer.analyze(_report([dep1, dep2]))
    assert [r.dependency_id for r in res] == ["d1", "d2"]

def test_input_immutability(analyzer):
    """17. input immutability"""
    ua = DependencyUpgradeAnalysis()
    dep = _dep(upgrade_analysis=ua)
    report = _report([dep])

    analyzer.analyze(report)
    assert len(report.dependencies) == 1

def test_missing_exact_command(analyzer):
    ua = DependencyUpgradeAnalysis(exact_upgrade_command=None)
    dep = _dep(upgrade_analysis=ua)
    res = analyzer.analyze(_report([dep]))[0]

    assert res.exact_upgrade_command == "UNKNOWN"
    assert res.requires_manual_review is True

def test_dependency_without_upgrade_analysis(analyzer):
    dep = _dep(upgrade_analysis=None)
    res = analyzer.analyze(_report([dep]))
    assert len(res) == 0

def test_json_rendering():
    """20. JSON rendering"""
    ua = DependencyUpgradeAnalysis()
    report = _report([_dep(upgrade_analysis=ua)])
    doc = ReportDocument.from_report_data(report)
    raw = JsonExporter().export(doc)
    data = json.loads(raw)

    section_titles = [s["title"] for s in data["sections"]]
    assert "A. Pre-Upgrade Checklist" in section_titles
    assert "B. Upgrade & Rollback Plan" in section_titles
    assert "C. Post-Upgrade Validation Matrix" in section_titles

def test_html_rendering():
    """21. HTML rendering"""
    ua = DependencyUpgradeAnalysis()
    report = _report([_dep(upgrade_analysis=ua)])
    doc = ReportDocument.from_report_data(report)
    html = HtmlExporter().export(doc).decode("utf-8")
    assert "Post-Upgrade Validation Matrix" in html

def test_pdf_rendering():
    """22. PDF rendering"""
    ua = DependencyUpgradeAnalysis()
    report = _report([_dep(upgrade_analysis=ua)])
    doc = ReportDocument.from_report_data(report)
    pdf = PdfExporter().export(doc)
    assert isinstance(pdf, bytes)
    assert len(pdf) > 0
