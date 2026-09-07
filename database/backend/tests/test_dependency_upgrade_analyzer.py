import pytest
from app.services.reporting.report_data import ReportDependencyData, ReportVulnerabilityData
from app.services.reporting.analyzer.dependency_upgrade_analyzer import DependencyUpgradeAnalyzer

@pytest.fixture
def analyzer():
    return DependencyUpgradeAnalyzer()

def test_npm_semver_behavior(analyzer):
    dep = ReportDependencyData(id="d1", package_name="axios", ecosystem="npm", package_version="0.21.0", dependency_type="direct", is_direct=True)
    vulns = [
        ReportVulnerabilityData(dependency_id="d1", vulnerability_id="CVE-1", title="SSRF", severity="HIGH", finding_metadata={"patched_version": "0.21.1"})
    ]
    analysis = analyzer.analyze(dep, vulns)
    assert analysis.recommended_version == "0.21.1"
    assert not analysis.manual_review_required

def test_pip_pep440_behavior(analyzer):
    dep = ReportDependencyData(id="d1", package_name="requests", ecosystem="pypi", package_version="2.25.0", dependency_type="direct", is_direct=True)
    vulns = [
        ReportVulnerabilityData(dependency_id="d1", vulnerability_id="CVE-1", title="SSRF", severity="HIGH", finding_metadata={"patched_version": "2.25.1"})
    ]
    analysis = analyzer.analyze(dep, vulns)
    assert analysis.recommended_version == "2.25.1"
    assert analysis.exact_upgrade_command == "pip install requests==2.25.1"
    assert not analysis.manual_review_required

def test_lowest_risk_secure_target_selection(analyzer):
    # Multiple candidate paths. We want the one closest to current version.
    dep = ReportDependencyData(id="d1", package_name="axios", ecosystem="npm", package_version="1.2.0", dependency_type="direct", is_direct=True)
    vulns = [
        # Vuln 1 fixed in 1.2.5 and 2.0.1
        ReportVulnerabilityData(dependency_id="d1", vulnerability_id="CVE-1", title="Vuln 1", severity="HIGH", finding_metadata={"patched_version": "1.2.5, 2.0.1"}),
        # Vuln 2 fixed in 1.2.4 and 2.0.0
        ReportVulnerabilityData(dependency_id="d1", vulnerability_id="CVE-2", title="Vuln 2", severity="MEDIUM", finding_metadata={"patched_version": "1.2.4, 2.0.0"})
    ]
    analysis = analyzer.analyze(dep, vulns)
    # minimum overall valid fix candidate >= 1.2.0 is 1.2.4
    assert analysis.minimum_fixed_version == "1.2.4"
    # recommended is 1.2.5 (resolves both)
    assert analysis.recommended_version == "1.2.5"
    assert "CVE-1" in analysis.resolved_vulnerabilities
    assert "CVE-2" in analysis.resolved_vulnerabilities
    assert analysis.upgrade_risk == "LOW"

def test_latest_version_newer_than_recommended(analyzer):
    dep = ReportDependencyData(id="d1", package_name="axios", ecosystem="npm", package_version="0.21.0", dependency_type="direct", is_direct=True, registry_metadata={"latest_version": "1.6.0"})
    vulns = [
        ReportVulnerabilityData(dependency_id="d1", vulnerability_id="CVE-1", title="SSRF", severity="HIGH", finding_metadata={"patched_version": "0.21.1"})
    ]
    analysis = analyzer.analyze(dep, vulns)
    assert analysis.recommended_version == "0.21.1"
    assert analysis.latest_known_version == "1.6.0"

def test_multiple_vulnerabilities_different_fixed_versions(analyzer):
    dep = ReportDependencyData(id="d1", package_name="axios", ecosystem="npm", package_version="1.2.0", dependency_type="direct", is_direct=True)
    vulns = [
        # Vuln 1 fixed in 1.2.5
        ReportVulnerabilityData(dependency_id="d1", vulnerability_id="CVE-1", title="Vuln 1", severity="HIGH", finding_metadata={"patched_version": "1.2.5"}),
        # Vuln 2 fixed in 1.3.0
        ReportVulnerabilityData(dependency_id="d1", vulnerability_id="CVE-2", title="Vuln 2", severity="CRITICAL", finding_metadata={"patched_version": "1.3.0"})
    ]
    analysis = analyzer.analyze(dep, vulns)
    assert analysis.minimum_fixed_version == "1.2.5"
    assert analysis.recommended_version == "1.3.0"
    assert "CVE-1" in analysis.resolved_vulnerabilities
    assert "CVE-2" in analysis.resolved_vulnerabilities
    assert analysis.upgrade_risk == "MEDIUM"
    assert analysis.security_benefit == "CRITICAL"

def test_no_verified_fix(analyzer):
    dep = ReportDependencyData(id="d1", package_name="axios", ecosystem="npm", package_version="0.21.0", dependency_type="direct", is_direct=True)
    vulns = [
        ReportVulnerabilityData(dependency_id="d1", vulnerability_id="CVE-1", title="SSRF", severity="HIGH", finding_metadata={"patched_version": "0.21.1"})
    ]
    analysis = analyzer.analyze(dep, vulns)
    assert analysis.minimum_fixed_version == "0.21.1"
    assert analysis.recommended_version == "0.21.1"
    assert analysis.resolved_vulnerabilities == ["CVE-1"]
    assert not analysis.manual_review_required
    assert analysis.upgrade_risk == "LOW"

def test_unsupported_version_format(analyzer):
    dep = ReportDependencyData(id="d1", package_name="axios", ecosystem="npm", package_version="invalid-version", dependency_type="direct", is_direct=True)
    vulns = [
        ReportVulnerabilityData(dependency_id="d1", vulnerability_id="CVE-1", title="SSRF", severity="HIGH", finding_metadata={"patched_version": "0.21.1"})
    ]
    analysis = analyzer.analyze(dep, vulns)
    # manual review because comparison fails
    assert analysis.manual_review_required

def test_manual_review_unsupported_ecosystem(analyzer):
    dep = ReportDependencyData(id="d1", package_name="lib", ecosystem="unknown-eco", package_version="1.0.0", dependency_type="direct", is_direct=True)
    vulns = [
        ReportVulnerabilityData(dependency_id="d1", vulnerability_id="CVE-1", title="SSRF", severity="HIGH", finding_metadata={"patched_version": "1.0.1"})
    ]
    analysis = analyzer.analyze(dep, vulns)
    assert analysis.manual_review_required

def test_unresolvable_fix_lower_than_current_version_forces_manual_review(analyzer):
    # Current version is 3.0.0. The vulnerability says patched in 2.0.0.
    # The analyzer cannot assume 3.0.0 is secure unless it's explicitly stated or > 2.0.0.
    # Wait, if 3.0.0 > 2.0.0, the analyzer DOES assume it's secure if 3.0.0 was a candidate.
    # But 3.0.0 is NOT a candidate. The only candidate is 2.0.0.
    # Since 2.0.0 < 3.0.0, 2.0.0 is discarded (downgrade).
    # Thus, no valid candidates remain, forcing manual review.
    dep = ReportDependencyData(id="d1", package_name="axios", ecosystem="npm", package_version="3.0.0", dependency_type="direct", is_direct=True)
    vulns = [
        ReportVulnerabilityData(dependency_id="d1", vulnerability_id="CVE-1", title="Vuln 1", severity="HIGH", finding_metadata={"patched_version": "2.0.0"})
    ]
    analysis = analyzer.analyze(dep, vulns)
    assert analysis.recommended_version is None
    assert analysis.manual_review_required
    assert analysis.minimum_fixed_version is None

def test_semver_library_behavior(analyzer):
    # This tests the native semver library behavior
    dep = ReportDependencyData(id="d1", package_name="axios", ecosystem="npm", package_version="1.2.0-alpha.1", dependency_type="direct", is_direct=True)
    vulns = [
        ReportVulnerabilityData(dependency_id="d1", vulnerability_id="CVE-1", title="Vuln 1", severity="HIGH", finding_metadata={"patched_version": "1.2.0-beta.1"})
    ]
    analysis = analyzer.analyze(dep, vulns)
    assert analysis.recommended_version == "1.2.0-beta.1"
    assert analysis.upgrade_risk == "LOW"
