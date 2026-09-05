import pytest
from app.services.reporting.report_data import (
    ReportData,
    DependencyUpgradeAnalysis,
    BreakingChangeData,
    CodeImpactData,
    FailureRiskData,
    ReportSafeUpgradePlan
)
from app.services.reporting.report_document import ReportDocument

def test_report_data_parses_phase_b_structures():
    snapshot = {
        "metadata": {"schema_version": "1.0.0"},
        "canonical_payload": {
            "project": {"id": "p1", "name": "Test Project"},
            "scan": {
                "id": "s1",
                "scan_type": "security",
                "scanner_version": "1.0",
                "started_at": "2026-09-01T00:00:00Z",
                "completed_at": "2026-09-01T00:01:00Z"
            },
            "summary": {
                "total_packages": 1,
                "vulnerable_packages": 1,
                "vulnerability_findings": 1,
                "severity_counts": {"CRITICAL": 1, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
            },
            "dependencies": [
                {
                    "id": "d1",
                    "package_name": "axios",
                    "ecosystem": "npm",
                    "package_version": "0.21.0",
                    "dependency_type": "direct",
                    "is_direct": True,
                    "registry_metadata": {"outdated": True},
                    "upgrade_analysis": {
                        "minimum_fixed_version": "0.21.1",
                        "recommended_version": "0.21.4",
                        "latest_known_version": "1.6.0",
                        "manual_review_required": True,
                        "upgrade_risk": "MEDIUM",
                        "security_benefit": "HIGH",
                        "compatibility_risk": "LOW",
                        "breaking_changes": [
                            {"category": "POTENTIAL", "description": "API changed", "impact": "LOW"}
                        ],
                        "code_impacts": [
                            {"file_path": "src/api.ts", "line_number": 42, "detected_pattern": "axios.get", "risk": "LOW", "recommendation": "Review usage"}
                        ],
                        "failure_risks": [
                            {"scenario": "Build fail", "risk": "LOW", "trigger": "Type mismatch", "affected_area": "Build", "prevention": "Type check"}
                        ],
                        "exact_upgrade_command": "npm install axios@0.21.4"
                    }
                }
            ],
            "vulnerabilities": [
                {
                    "dependency_id": "d1",
                    "vulnerability_id": "CVE-2021-1234",
                    "title": "SSRF",
                    "severity": "CRITICAL",
                    "remediation_status": "In Progress"
                }
            ],
            "safe_upgrade_plan": {
                "before_upgrade": ["Backup lock file"],
                "during_upgrade": ["npm install"],
                "after_upgrade": ["Run tests"]
            }
        }
    }

    report_data = ReportData.from_snapshot(snapshot)
    assert len(report_data.dependencies) == 1
    dep = report_data.dependencies[0]
    assert dep.upgrade_analysis is not None
    assert dep.upgrade_analysis.recommended_version == "0.21.4"
    assert len(dep.upgrade_analysis.breaking_changes) == 1
    assert dep.upgrade_analysis.breaking_changes[0].category == "POTENTIAL"

    assert report_data.safe_upgrade_plan is not None
    assert "Backup lock file" in report_data.safe_upgrade_plan.before_upgrade

    # Test document generation
    doc = ReportDocument.from_report_data(report_data)
    assert doc.title == "Security Dependency Report"

    # Find Upgrade Analysis Section
    ua_sections = [s for s in doc.sections if s.title.startswith("Upgrade Analysis")]
    assert len(ua_sections) == 1
    ua_sec = ua_sections[0]

    # Check tables in UA section
    assert len(ua_sec.tables) == 3
    assert ua_sec.tables[0].title == "Breaking Changes"
    assert ua_sec.tables[1].title == "Source Code Impact"
    assert ua_sec.tables[2].title == "Potential Failure Risks"

    # Find Safe Upgrade Plan Section
    plan_sections = [s for s in doc.sections if s.title == "Safe Upgrade Plan"]
    assert len(plan_sections) == 1
    plan_sec = plan_sections[0]
    assert "BEFORE UPGRADE" in plan_sec.content
