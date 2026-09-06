import pytest
from app.services.reporting.report_document import ReportDocument
from app.services.reporting.report_data import ReportData

def test_report_document_ordering_and_new_sections():
    # Using snapshot_data fixture from conftest if available, or we just mock a minimal ReportData
    from app.services.reporting.report_data import ReportData, ReportProjectData, ReportScanData, ReportSummaryData

    data = ReportData(
        metadata={"document_schema_version": "1.0.0", "generator_version": "test", "snapshot_sha256": "abc", "created_at": "now", "report_id": "r1"},
        project=ReportProjectData(id="p1", name="Test Project"),
        scan=ReportScanData(id="s1", scan_type="type", scanner_version="v1", started_at=None, completed_at=None),
        summary=ReportSummaryData(total_packages=10, vulnerable_packages=2, vulnerability_findings=2, outdated_packages=1, unknown_packages=0, severity_counts={}),
        dependencies=[],
        vulnerabilities=[]
    )

    doc = ReportDocument.from_report_data(data)

    # Assert cover exists and is first
    assert doc.sections[0].title == "Report Cover"
    assert "Test Project" in doc.sections[0].content

    # Assert Dashboard exists and has new metrics
    assert doc.sections[1].title == "Executive Summary"
    labels = [m.label for m in doc.sections[1].metrics]
    assert "Manual Reviews Required" in labels
    assert "Fix Evidence Available" in labels
    assert "Verified Remediated" in labels

    # Assert Methodology exists
    methodology_sections = [s for s in doc.sections if s.title == "Methodology & Data Sources"]
    assert len(methodology_sections) == 1
    assert "Offline, read-only analysis" in methodology_sections[0].content

    # Assert Final Recommendation exists and is last
    assert doc.sections[-1].title == "Final Recommendation"
    assert "No actionable security upgrades identified" in doc.sections[-1].content # Because dependencies is empty

def test_final_recommendation_logic():
    from app.services.reporting.report_data import ReportData, ReportProjectData, ReportScanData, ReportSummaryData, ReportDependencyData, ReportVulnerabilityData, DependencyUpgradeAnalysis, FailureRiskData

    # 1. Manual review required without high compatibility/failure risk
    data1 = ReportData(
        metadata={}, project=ReportProjectData(id="p", name="n"), scan=ReportScanData(id="s", scan_type="t", scanner_version="v", started_at=None, completed_at=None),
        summary=ReportSummaryData(total_packages=0, vulnerable_packages=0, vulnerability_findings=0, outdated_packages=0, unknown_packages=0, severity_counts={}),
        dependencies=[ReportDependencyData(
            id="d1", package_name="pkg", ecosystem="npm", package_version="1", dependency_type="PROD", is_direct=True, outdated="FALSE", registry_metadata={},
            upgrade_analysis=DependencyUpgradeAnalysis(manual_review_required=True, compatibility_risk="LOW")
        )],
        vulnerabilities=[]
    )
    doc1 = ReportDocument.from_report_data(data1)
    assert "Manual review required. Automated upgrade paths are unavailable or require human verification." in doc1.sections[-1].content
    assert "High compatibility or application failure risk detected." not in doc1.sections[-1].content

    # 2. High compatibility risk
    data2 = ReportData(
        metadata={}, project=ReportProjectData(id="p", name="n"), scan=ReportScanData(id="s", scan_type="t", scanner_version="v", started_at=None, completed_at=None),
        summary=ReportSummaryData(total_packages=0, vulnerable_packages=0, vulnerability_findings=0, outdated_packages=0, unknown_packages=0, severity_counts={}),
        dependencies=[ReportDependencyData(
            id="d1", package_name="pkg", ecosystem="npm", package_version="1", dependency_type="PROD", is_direct=True, outdated="FALSE", registry_metadata={},
            upgrade_analysis=DependencyUpgradeAnalysis(manual_review_required=False, compatibility_risk="HIGH")
        )],
        vulnerabilities=[]
    )
    doc2 = ReportDocument.from_report_data(data2)
    assert "Manual review required. High compatibility or application failure risk detected." in doc2.sections[-1].content

    # 3. High failure risk
    data3 = ReportData(
        metadata={}, project=ReportProjectData(id="p", name="n"), scan=ReportScanData(id="s", scan_type="t", scanner_version="v", started_at=None, completed_at=None),
        summary=ReportSummaryData(total_packages=0, vulnerable_packages=0, vulnerability_findings=0, outdated_packages=0, unknown_packages=0, severity_counts={}),
        dependencies=[ReportDependencyData(
            id="d1", package_name="pkg", ecosystem="npm", package_version="1", dependency_type="PROD", is_direct=True, outdated="FALSE", registry_metadata={},
            upgrade_analysis=DependencyUpgradeAnalysis(manual_review_required=False, failure_risks=[FailureRiskData(scenario="s", risk="CRITICAL", trigger="t", affected_area="a", prevention="p")])
        )],
        vulnerabilities=[]
    )
    doc3 = ReportDocument.from_report_data(data3)
    assert "Manual review required. High compatibility or application failure risk detected." in doc3.sections[-1].content

    # 4. Fixes available + no follow-up
    data4 = ReportData(
        metadata={}, project=ReportProjectData(id="p", name="n"), scan=ReportScanData(id="s", scan_type="t", scanner_version="v", started_at=None, completed_at=None),
        summary=ReportSummaryData(total_packages=0, vulnerable_packages=0, vulnerability_findings=0, outdated_packages=0, unknown_packages=0, severity_counts={}),
        dependencies=[ReportDependencyData(
            id="d1", package_name="pkg", ecosystem="npm", package_version="1", dependency_type="PROD", is_direct=True, outdated="FALSE", registry_metadata={},
            upgrade_analysis=DependencyUpgradeAnalysis(exact_upgrade_command="cmd", manual_review_required=False, resolved_vulnerabilities=["V1"])
        )],
        vulnerabilities=[ReportVulnerabilityData(dependency_id="d1", vulnerability_id="V1", title="T", severity="HIGH", remediation_status="NO FOLLOW-UP SCAN")]
    )
    doc4 = ReportDocument.from_report_data(data4)
    assert "Actionable upgrade paths exist." in doc4.sections[-1].content
    assert "Follow-up security validation required." in doc4.sections[-1].content

    # 5. Verified still present
    data5 = ReportData(
        metadata={}, project=ReportProjectData(id="p", name="n"), scan=ReportScanData(id="s", scan_type="t", scanner_version="v", started_at=None, completed_at=None),
        summary=ReportSummaryData(total_packages=0, vulnerable_packages=0, vulnerability_findings=0, outdated_packages=0, unknown_packages=0, severity_counts={}),
        dependencies=[],
        vulnerabilities=[ReportVulnerabilityData(dependency_id="d1", vulnerability_id="V1", title="T", severity="HIGH", remediation_status="VERIFIED STILL PRESENT")]
    )
    doc5 = ReportDocument.from_report_data(data5)
    assert "Verified still-present vulnerabilities detected" in doc5.sections[-1].content
    assert "The finding remains present in the available follow-up evidence." in doc5.sections[-1].content

    # 6. No actionable upgrade
    data6 = ReportData(
        metadata={}, project=ReportProjectData(id="p", name="n"), scan=ReportScanData(id="s", scan_type="t", scanner_version="v", started_at=None, completed_at=None),
        summary=ReportSummaryData(total_packages=0, vulnerable_packages=0, vulnerability_findings=0, outdated_packages=0, unknown_packages=0, severity_counts={}),
        dependencies=[],
        vulnerabilities=[]
    )
    doc6 = ReportDocument.from_report_data(data6)
    assert "No actionable security upgrades identified in this snapshot." in doc6.sections[-1].content
