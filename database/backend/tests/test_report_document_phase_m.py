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

    # Assert cover exists and is first.
    # Section titles are numbered (e.g. "1. Report Cover") — use substring match
    assert "Report Cover" in doc.sections[0].title
    assert "Test Project" in doc.sections[0].content

    # Assert Dashboard exists and has new metrics
    assert "Executive Summary" in doc.sections[1].title
    labels = [m.label for m in doc.sections[1].metrics]
    assert "Fix Evidence Available" in labels

    # Assert Methodology exists — use substring-tolerant search
    methodology_sections = [s for s in doc.sections if "Methodology" in s.title and "Data Sources" in s.title]
    assert len(methodology_sections) == 1
    # Methodology section uses "Offline, read-only analysis" or equivalent constraint language
    assert "Read-only analysis" in methodology_sections[0].content or "read-only" in methodology_sections[0].content.lower()

    # Assert Final Recommendation exists and is last — use substring match
    assert "Final Recommendation" in doc.sections[-1].title
    # With no dependencies and no vulnerabilities: no actionable security upgrades
    assert "No actionable security" in doc.sections[-1].content or "NO VERIFIED ACTION" in doc.sections[-1].content

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
    # With manual_review_required=True and no high risk, current production text:
    # "**INSUFFICIENT EVIDENCE FOR SAFE RECOMMENDATION.** Automated upgrade paths are missing or require human validation."
    final_content1 = doc1.sections[-1].content
    assert "INSUFFICIENT EVIDENCE" in final_content1 or "Manual review required" in final_content1
    assert "High compatibility" not in final_content1 or "High compatibility or application failure risk" not in final_content1

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
    # With high compatibility_risk: "**MANUAL SECURITY REVIEW REQUIRED.** High compatibility risks detected."
    final_content2 = doc2.sections[-1].content
    assert "MANUAL SECURITY REVIEW REQUIRED" in final_content2 or "High compatibility" in final_content2

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
    final_content3 = doc3.sections[-1].content
    assert "MANUAL SECURITY REVIEW REQUIRED" in final_content3 or "High compatibility" in final_content3

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
    # Current production: "**VERIFIED UPGRADE RECOMMENDED.** Clear upgrade paths exist..."
    final_content4 = doc4.sections[-1].content
    assert "VERIFIED UPGRADE RECOMMENDED" in final_content4 or "Actionable upgrade paths" in final_content4

    # 5. Verified still present
    data5 = ReportData(
        metadata={}, project=ReportProjectData(id="p", name="n"), scan=ReportScanData(id="s", scan_type="t", scanner_version="v", started_at=None, completed_at=None),
        summary=ReportSummaryData(total_packages=0, vulnerable_packages=0, vulnerability_findings=0, outdated_packages=0, unknown_packages=0, severity_counts={}),
        dependencies=[],
        vulnerabilities=[ReportVulnerabilityData(dependency_id="d1", vulnerability_id="V1", title="T", severity="HIGH", remediation_status="VERIFIED STILL PRESENT")]
    )
    doc5 = ReportDocument.from_report_data(data5)
    # Current production: "**MANUAL SECURITY REVIEW REQUIRED.** Verified still-present vulnerabilities without clean fixes detected."
    final_content5 = doc5.sections[-1].content
    assert "MANUAL SECURITY REVIEW REQUIRED" in final_content5 or "Verified still-present vulnerabilities" in final_content5

    # 6. No actionable upgrade
    data6 = ReportData(
        metadata={}, project=ReportProjectData(id="p", name="n"), scan=ReportScanData(id="s", scan_type="t", scanner_version="v", started_at=None, completed_at=None),
        summary=ReportSummaryData(total_packages=0, vulnerable_packages=0, vulnerability_findings=0, outdated_packages=0, unknown_packages=0, severity_counts={}),
        dependencies=[],
        vulnerabilities=[]
    )
    doc6 = ReportDocument.from_report_data(data6)
    # Current production: "**NO VERIFIED ACTION REQUIRED.** No actionable security vulnerabilities identified."
    final_content6 = doc6.sections[-1].content
    assert "NO VERIFIED ACTION REQUIRED" in final_content6 or "No actionable security" in final_content6
