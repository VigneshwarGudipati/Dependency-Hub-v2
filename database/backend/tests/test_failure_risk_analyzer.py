import pytest
from app.services.reporting.report_data import (
    DependencyUpgradeAnalysis,
    CodeImpactData,
    BreakingChangeData,
)
from app.services.reporting.analyzer.failure_risk_analyzer import FailureRiskAnalyzer


@pytest.fixture
def analyzer():
    return FailureRiskAnalyzer()


def test_no_failure_risk_evidence(analyzer):
    # Requirement 1: no failure-risk evidence -> LOW risk
    ua = DependencyUpgradeAnalysis(recommended_version="1.0.1", compatibility_risk="LOW")
    res = analyzer.analyze(ua, [])
    assert len(res.failure_risks) == 1
    assert res.failure_risks[0].risk == "LOW"
    assert res.failure_risks[0].scenario == "No material failure signal identified"


def test_direct_source_usage_and_potential_compatibility_concern(analyzer):
    # Requirement 2: direct source usage + potential compatibility concern
    # Requirement 3: multiple affected files
    ua = DependencyUpgradeAnalysis(recommended_version="2.0.0", compatibility_risk="HIGH")
    impacts = [
        CodeImpactData(file_path="src/a.py", detected_pattern="import x", risk="MEDIUM", recommendation=""),
        CodeImpactData(file_path="src/b.py", detected_pattern="import x", risk="MEDIUM", recommendation=""),
    ]
    res = analyzer.analyze(ua, impacts)
    assert res.failure_risks[0].risk == "HIGH"
    assert "multiple files" in res.failure_risks[0].trigger
    assert res.failure_risks[0].scenario == "Potential application failure risk from dependency compatibility change"


def test_major_version_transition_no_source_usage(analyzer):
    # Requirement 4: major-version transition -> MEDIUM risk if no source usage
    ua = DependencyUpgradeAnalysis(recommended_version="2.0.0", compatibility_risk="MEDIUM")
    res = analyzer.analyze(ua, [])
    assert res.failure_risks[0].risk == "MEDIUM"
    assert "without identified direct source usage" in res.failure_risks[0].trigger


def test_verified_breaking_evidence_without_application_impact(analyzer):
    # Requirement: verified authoritative breaking evidence + generic source usage -> POTENTIAL + HIGH
    ua = DependencyUpgradeAnalysis(
        recommended_version="2.0.0",
        compatibility_risk="HIGH",
        breaking_changes=[BreakingChangeData(category="VERIFIED", description="API removed", impact="High")]
    )
    impacts = [CodeImpactData(file_path="src/a.py", detected_pattern="import x", risk="MEDIUM", recommendation="")]
    res = analyzer.analyze(ua, impacts)
    assert res.failure_risks[0].risk == "HIGH"
    assert res.failure_risks[0].scenario == "Potential application failure risk from verified breaking change"
    assert "generic source usage" in res.failure_risks[0].trigger

def test_verified_breaking_evidence_with_authoritative_impact(analyzer):
    # Requirement: verified breaking change evidence + authoritative proof that application's actual usage is affected -> VERIFIED
    ua = DependencyUpgradeAnalysis(
        recommended_version="2.0.0",
        compatibility_risk="HIGH",
        breaking_changes=[BreakingChangeData(category="VERIFIED", description="API removed", impact="High")]
    )
    impacts = [CodeImpactData(file_path="src/a.py", detected_pattern="import x", risk="VERIFIED", recommendation="")]
    res = analyzer.analyze(ua, impacts)
    assert res.failure_risks[0].risk == "VERIFIED"


def test_no_false_verified_classification(analyzer):
    # Requirement 6: no false VERIFIED classification
    ua = DependencyUpgradeAnalysis(recommended_version="2.0.0", compatibility_risk="HIGH")
    impacts = [CodeImpactData(file_path="src/a.py", detected_pattern="import x", risk="MEDIUM", recommendation="")]
    res = analyzer.analyze(ua, impacts)
    assert res.failure_risks[0].risk == "HIGH"
    # Should not be VERIFIED despite major version + source usage
    assert res.failure_risks[0].risk != "VERIFIED"


def test_unsupported_ecosystem(analyzer):
    # Requirement 7: unsupported ecosystem (compatibility_risk = "UNKNOWN")
    ua = DependencyUpgradeAnalysis(recommended_version="2.0.0", compatibility_risk="UNKNOWN")
    res = analyzer.analyze(ua, [])
    assert res.failure_risks[0].risk == "UNKNOWN"
    assert res.failure_risks[0].scenario == "Unsupported ecosystem or missing data"


def test_missing_upgrade_data(analyzer):
    # Requirement 8: missing upgrade data
    # Requirement 9: safe handling of partial/unknown data
    ua = DependencyUpgradeAnalysis(recommended_version=None)
    res = analyzer.analyze(ua, [])
    assert res.failure_risks[0].risk == "MANUAL REVIEW REQUIRED"
    assert res.failure_risks[0].scenario == "Missing upgrade data"


def test_crash_wording_safety(analyzer):
    # Requirement 10: crash wording safety
    ua = DependencyUpgradeAnalysis(recommended_version="2.0.0", compatibility_risk="HIGH")
    impacts = [CodeImpactData(file_path="src/a.py", detected_pattern="import x", risk="MEDIUM", recommendation="")]
    res = analyzer.analyze(ua, impacts)
    text = f"{res.failure_risks[0].scenario} {res.failure_risks[0].trigger} {res.failure_risks[0].prevention}".lower()

    # Must not contain unconditional crash language
    assert "will crash" not in text
    assert "definitely fail" not in text
    assert "break production" not in text

    # Should contain cautious language
    assert "potential application failure risk" in text
    assert "validation required" in text
