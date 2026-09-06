import pytest
from app.services.reporting.report_data import (
    ReportDependencyData,
    DependencyUpgradeAnalysis,
    CodeImpactData,
)
from app.services.reporting.analyzer.compatibility_analyzer import CompatibilityAnalyzer


@pytest.fixture
def analyzer():
    return CompatibilityAnalyzer()


def test_no_compatibility_evidence(analyzer):
    # Requirement 1: no compatibility evidence -> MANUAL REVIEW REQUIRED
    # Requirement 9: migration guidance unavailable
    dep = ReportDependencyData(id="d1", package_name="requests", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    ua = DependencyUpgradeAnalysis(recommended_version="2.1.0")

    res = analyzer.analyze(dep, ua, [])
    assert res.compatibility_risk == "LOW"
    assert res.manual_review_required is True


def test_major_version_potential_risk(analyzer):
    # Requirement 2: major-version potential risk -> POTENTIAL, not VERIFIED (Requirement 8)
    dep = ReportDependencyData(id="d1", package_name="requests", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    ua = DependencyUpgradeAnalysis(recommended_version="3.0.0")

    res = analyzer.analyze(dep, ua, [])
    assert res.compatibility_risk == "MEDIUM"
    assert res.manual_review_required is True


def test_verified_breaking_change_evidence(analyzer):
    # Requirement 3: verified breaking-change evidence
    dep = ReportDependencyData(
        id="d1", package_name="requests", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True,
        registry_metadata={"breaking_change_evidence": "API removed in 3.x"}
    )
    ua = DependencyUpgradeAnalysis(recommended_version="3.0.0")

    res = analyzer.analyze(dep, ua, [])
    assert res.compatibility_risk == "HIGH"
    assert res.manual_review_required is True
    assert len(res.breaking_changes) == 1
    assert res.breaking_changes[0].category == "VERIFIED"
    assert res.breaking_changes[0].description == "API removed in 3.x"


def test_manual_review_result(analyzer):
    # Requirement 4: manual-review result
    dep = ReportDependencyData(id="d1", package_name="requests", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    ua = DependencyUpgradeAnalysis(recommended_version="2.0.1")

    res = analyzer.analyze(dep, ua, [])
    assert res.compatibility_risk == "LOW"
    assert res.manual_review_required is True


def test_unsupported_ecosystem(analyzer):
    # Requirement 5: unsupported ecosystem -> UNKNOWN
    dep = ReportDependencyData(id="d1", package_name="lib", ecosystem="unknown-eco", package_version="1.0.0", dependency_type="direct", is_direct=True)
    ua = DependencyUpgradeAnalysis(recommended_version="2.0.0")

    res = analyzer.analyze(dep, ua, [])
    assert res.compatibility_risk == "UNKNOWN"
    assert res.manual_review_required is True


def test_source_impact_integration_and_multiple_files(analyzer):
    # Requirement 6: source-impact integration
    # Requirement 7: multiple affected files
    dep = ReportDependencyData(id="d1", package_name="requests", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    ua = DependencyUpgradeAnalysis(recommended_version="3.0.0")

    code_impacts = [
        CodeImpactData(file_path="src/main.py", detected_pattern="import requests", risk="MEDIUM", recommendation=""),
        CodeImpactData(file_path="src/api.py", detected_pattern="import requests", risk="MEDIUM", recommendation=""),
        CodeImpactData(file_path="src/api.py", detected_pattern="from requests import get", risk="MEDIUM", recommendation=""),
    ]

    res = analyzer.analyze(dep, ua, code_impacts)
    assert res.compatibility_risk == "HIGH"
    assert res.manual_review_required is True


def test_no_false_verified_classification(analyzer):
    # Requirement 8: no false VERIFIED classification
    # Even with major version AND source impact, it must NOT be VERIFIED.
    dep = ReportDependencyData(id="d1", package_name="requests", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    ua = DependencyUpgradeAnalysis(recommended_version="3.0.0")
    code_impacts = [CodeImpactData(file_path="src/main.py", detected_pattern="import requests", risk="MEDIUM", recommendation="")]

    res = analyzer.analyze(dep, ua, code_impacts)
    assert not any(bc.category == "VERIFIED" for bc in res.breaking_changes)


def test_missing_or_partial_upgrade_data(analyzer):
    # Requirement 10: missing/partial upgrade data
    dep = ReportDependencyData(id="d1", package_name="requests", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    ua = DependencyUpgradeAnalysis(recommended_version=None)  # Missing recommendation

    res = analyzer.analyze(dep, ua, [])
    assert res.compatibility_risk == "UNKNOWN"
    assert res.manual_review_required is True
