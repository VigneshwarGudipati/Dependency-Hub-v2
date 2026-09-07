import pytest

from app.services.reporting.report_data import (
    ReportData,
    ReportProjectData,
    ReportScanData,
    ReportSummaryData,
    ReportSeverityCounts,
    ReportDependencyData,
    ReportVulnerabilityData,
)
from app.services.reporting.analyzer.scan_comparison_analyzer import (
    ScanComparisonAnalyzer,
    ScanComparisonResult,
    VulnerabilityComparisonResult,
)

# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------

_PROJECT_ID = "project-uuid-1"
_OTHER_PROJECT_ID = "project-uuid-2"
_ORG_ID = "org-uuid-1"

_FORBIDDEN_CAUSAL_WORDS = [
    "fixed",
    "resolved",
    "caused",
    "upgrade fixed",
    "upgrade caused",
    "remediation was successful",
    "the upgrade",
]


def _make_dep(
    dep_id: str,
    package_name: str,
    ecosystem: str,
    package_version: str,
) -> ReportDependencyData:
    return ReportDependencyData(
        id=dep_id,
        package_name=package_name,
        ecosystem=ecosystem,
        package_version=package_version,
        dependency_type="RUNTIME",
        is_direct=True,
    )


def _make_vuln(
    vulnerability_id: str,
    dependency_id: str,
    title: str = "Test Vulnerability",
    severity: str = "HIGH",
) -> ReportVulnerabilityData:
    return ReportVulnerabilityData(
        dependency_id=dependency_id,
        vulnerability_id=vulnerability_id,
        title=title,
        severity=severity,
    )


def _make_report(
    project_id: str,
    scan_id: str,
    dependencies: list,
    vulnerabilities: list,
    org_id: str = _ORG_ID,
) -> ReportData:
    return ReportData(
        metadata={
            "project_id": project_id,
            "scan_id": scan_id,
            "organization_id": org_id,
            "schema_version": "1.0.0",
            "snapshot_sha256": "deadbeef",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
        project=ReportProjectData(id=project_id, name="Test Project"),
        scan=ReportScanData(
            id=scan_id,
            scan_type="FULL",
            started_at=None,
            completed_at=None,
            scanner_version="1.0.0",
        ),
        summary=ReportSummaryData(
            total_packages=len(dependencies),
            vulnerable_packages=len({v.dependency_id for v in vulnerabilities}),
            vulnerability_findings=len(vulnerabilities),
            severity_counts=ReportSeverityCounts(),
        ),
        dependencies=dependencies,
        vulnerabilities=vulnerabilities,
    )


@pytest.fixture
def analyzer() -> ScanComparisonAnalyzer:
    return ScanComparisonAnalyzer()


# ---------------------------------------------------------------------------
# Test 1 — no follow-up scan
# ---------------------------------------------------------------------------

def test_no_followup_scan(analyzer):
    dep = _make_dep("dep-1", "axios", "npm", "0.21.0")
    vuln = _make_vuln("CVE-2021-0001", "dep-1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep], [vuln])

    result = analyzer.analyze(baseline, None)

    assert isinstance(result, ScanComparisonResult)
    assert result.comparison_status == "NO FOLLOW-UP SCAN"
    assert result.baseline_scan_id == "scan-base-1"
    assert result.followup_scan_id is None
    assert result.project_id == _PROJECT_ID
    assert len(result.findings) == 1

    f = result.findings[0]
    assert f.comparison_status == "NO FOLLOW-UP SCAN"
    assert f.vulnerability_id == "CVE-2021-0001"
    assert f.dependency_key == "axios::npm"
    assert f.baseline_version == "0.21.0"
    assert f.followup_version is None


# ---------------------------------------------------------------------------
# Test 2 — no baseline
# ---------------------------------------------------------------------------

def test_no_baseline(analyzer):
    dep = _make_dep("dep-f1", "axios", "npm", "1.0.0")
    vuln = _make_vuln("CVE-2021-0001", "dep-f1")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep], [vuln])

    result = analyzer.analyze(None, followup)

    assert result.comparison_status == "MANUAL REVIEW REQUIRED"
    assert result.baseline_scan_id is None
    assert result.followup_scan_id == "scan-follow-1"
    assert result.project_id == _PROJECT_ID
    assert len(result.findings) == 1

    f = result.findings[0]
    assert f.comparison_status == "MANUAL REVIEW REQUIRED"
    assert f.vulnerability_id == "CVE-2021-0001"
    assert f.dependency_key == "axios::npm"
    assert f.baseline_version is None
    assert f.followup_version == "1.0.0"
    assert "No baseline snapshot was supplied" in (f.comparison_note or "")


# ---------------------------------------------------------------------------
# Test 3 — verified remediation
# ---------------------------------------------------------------------------

def test_verified_remediated(analyzer):
    dep_b = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    vuln_b = _make_vuln("CVE-2021-0001", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b])

    dep_f = _make_dep("dep-f1", "axios", "npm", "1.0.0")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [])

    result = analyzer.analyze(baseline, followup)

    assert result.comparison_status == "VERIFIED REMEDIATED"
    assert len(result.findings) == 1

    f = result.findings[0]
    assert f.comparison_status == "VERIFIED REMEDIATED"
    assert f.vulnerability_id == "CVE-2021-0001"
    assert f.dependency_key == "axios::npm"
    assert f.baseline_version == "0.21.0"
    assert f.followup_version == "1.0.0"
    assert "absent from the complete follow-up scan" in (f.comparison_note or "")


# ---------------------------------------------------------------------------
# Test 4 — verified still present
# ---------------------------------------------------------------------------

def test_verified_still_present(analyzer):
    dep_b = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    vuln_b = _make_vuln("CVE-2021-0001", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b])

    dep_f = _make_dep("dep-f1", "axios", "npm", "0.21.0")
    vuln_f = _make_vuln("CVE-2021-0001", "dep-f1")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [vuln_f])

    result = analyzer.analyze(baseline, followup)

    assert result.comparison_status == "VERIFIED STILL PRESENT"
    assert len(result.findings) == 1

    f = result.findings[0]
    assert f.comparison_status == "VERIFIED STILL PRESENT"
    assert f.vulnerability_id == "CVE-2021-0001"
    assert f.dependency_key == "axios::npm"
    assert f.baseline_version == "0.21.0"
    assert f.followup_version == "0.21.0"


# ---------------------------------------------------------------------------
# Test 5 — partial remediation
# ---------------------------------------------------------------------------

def test_partial_remediation(analyzer):
    dep_b = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    vuln_b1 = _make_vuln("CVE-2021-0001", "dep-b1")
    vuln_b2 = _make_vuln("CVE-2021-0002", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b1, vuln_b2])

    dep_f = _make_dep("dep-f1", "axios", "npm", "1.0.0")
    # CVE-0001 absent (remediated); CVE-0002 still present
    vuln_f2 = _make_vuln("CVE-2021-0002", "dep-f1")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [vuln_f2])

    result = analyzer.analyze(baseline, followup)

    assert result.comparison_status == "PARTIALLY REMEDIATED"

    statuses = {f.vulnerability_id: f.comparison_status for f in result.findings}
    assert statuses["CVE-2021-0001"] == "VERIFIED REMEDIATED"
    assert statuses["CVE-2021-0002"] == "VERIFIED STILL PRESENT"

    # Verify per-finding fields
    f1 = next(f for f in result.findings if f.vulnerability_id == "CVE-2021-0001")
    assert f1.dependency_key == "axios::npm"
    assert f1.baseline_version == "0.21.0"

    f2 = next(f for f in result.findings if f.vulnerability_id == "CVE-2021-0002")
    assert f2.dependency_key == "axios::npm"
    assert f2.comparison_status == "VERIFIED STILL PRESENT"


# ---------------------------------------------------------------------------
# Test 6 — version changed but finding remains
# ---------------------------------------------------------------------------

def test_version_changed_finding_remains(analyzer):
    dep_b = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    vuln_b = _make_vuln("CVE-2021-0001", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b])

    dep_f = _make_dep("dep-f1", "axios", "npm", "1.2.0")
    vuln_f = _make_vuln("CVE-2021-0001", "dep-f1")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [vuln_f])

    result = analyzer.analyze(baseline, followup)

    assert result.comparison_status == "VERIFIED STILL PRESENT"
    assert len(result.findings) == 1

    f = result.findings[0]
    assert f.comparison_status == "VERIFIED STILL PRESENT"
    assert f.baseline_version == "0.21.0"
    assert f.followup_version == "1.2.0"
    # Version changed is noted but status is still VERIFIED STILL PRESENT,
    # not POTENTIAL CHANGE
    assert "1.2.0" in (f.comparison_note or "")


# ---------------------------------------------------------------------------
# Test 7 — version changed, finding absent: no causal claim
# ---------------------------------------------------------------------------

def test_version_changed_finding_absent_no_causal_claim(analyzer):
    dep_b = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    vuln_b = _make_vuln("CVE-2021-0001", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b])

    # Follow-up: axios upgraded to 1.2.0, CVE-0001 absent
    dep_f = _make_dep("dep-f1", "axios", "npm", "1.2.0")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [])

    result = analyzer.analyze(baseline, followup)

    assert result.comparison_status == "VERIFIED REMEDIATED"
    assert len(result.findings) == 1

    f = result.findings[0]
    assert f.comparison_status == "VERIFIED REMEDIATED"
    assert f.vulnerability_id == "CVE-2021-0001"
    assert f.baseline_version == "0.21.0"
    assert f.followup_version == "1.2.0"

    # Must record the version change
    note = f.comparison_note or ""
    assert "Dependency version changed from 0.21.0 to 1.2.0" in note

    # Must NOT claim causality
    note_lower = note.lower()
    for forbidden in _FORBIDDEN_CAUSAL_WORDS:
        assert forbidden.lower() not in note_lower, (
            f"Causal word {forbidden!r} found in comparison_note: {note!r}"
        )


# ---------------------------------------------------------------------------
# Test 8 — incomplete/failed follow-up not treated as remediation
# ---------------------------------------------------------------------------

def test_incomplete_followup_not_treated_as_remediation(analyzer):
    # The repository guarantees no ReportData exists for incomplete scans.
    # A None follow-up means no completed scan is available.
    dep_b = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    vuln_b = _make_vuln("CVE-2021-0001", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b])

    result = analyzer.analyze(baseline, None)

    assert result.comparison_status == "NO FOLLOW-UP SCAN"
    assert len(result.findings) == 1

    f = result.findings[0]
    assert f.comparison_status == "NO FOLLOW-UP SCAN"
    # No remediation claimed
    assert f.comparison_status != "VERIFIED REMEDIATED"
    assert f.comparison_status != "PARTIALLY REMEDIATED"


# ---------------------------------------------------------------------------
# Test 9 — stable finding identity (exact match)
# ---------------------------------------------------------------------------

def test_stable_finding_identity_exact_match(analyzer):
    # Confirms that cross-scan matching is exact vulnerability_id string equality
    vid = "GHSA-abcd-1234-efgh"
    dep_b = _make_dep("dep-b1", "requests", "pypi", "2.25.0")
    vuln_b = _make_vuln(vid, "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b])

    dep_f = _make_dep("dep-f1", "requests", "pypi", "2.28.0")
    vuln_f = _make_vuln(vid, "dep-f1")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [vuln_f])

    result = analyzer.analyze(baseline, followup)

    assert result.comparison_status == "VERIFIED STILL PRESENT"
    f = result.findings[0]
    assert f.vulnerability_id == vid
    assert f.comparison_status == "VERIFIED STILL PRESENT"


# ---------------------------------------------------------------------------
# Test 10 — missing/unstable identity → MANUAL REVIEW REQUIRED
# ---------------------------------------------------------------------------

def test_missing_unstable_identity(analyzer):
    dep_b = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    vuln_b = _make_vuln("UNKNOWN", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b])

    dep_f = _make_dep("dep-f1", "axios", "npm", "1.0.0")
    vuln_f = _make_vuln("UNKNOWN", "dep-f1")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [vuln_f])

    result = analyzer.analyze(baseline, followup)

    # Baseline UNKNOWN → MANUAL REVIEW REQUIRED; follow-up UNKNOWN → also MANUAL REVIEW REQUIRED
    for f in result.findings:
        assert f.comparison_status == "MANUAL REVIEW REQUIRED"
        assert "UNKNOWN" in f.vulnerability_id or "UNKNOWN" in f.comparison_status


# ---------------------------------------------------------------------------
# Test 11 — same project id proceeds normally
# ---------------------------------------------------------------------------

def test_same_project_id(analyzer):
    dep_b = _make_dep("dep-b1", "lodash", "npm", "4.17.20")
    vuln_b = _make_vuln("CVE-2021-9999", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b])

    dep_f = _make_dep("dep-f1", "lodash", "npm", "4.17.21")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [])

    result = analyzer.analyze(baseline, followup)

    # Comparison proceeds; no MANUAL REVIEW REQUIRED from project mismatch
    assert result.project_id == _PROJECT_ID
    assert result.comparison_status != "MANUAL REVIEW REQUIRED" or len(result.findings) > 0


# ---------------------------------------------------------------------------
# Test 12 — different project id
# ---------------------------------------------------------------------------

def test_different_project_id(analyzer):
    dep_b = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    vuln_b = _make_vuln("CVE-2021-0001", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b])

    dep_f = _make_dep("dep-f1", "axios", "npm", "1.0.0")
    vuln_f = _make_vuln("CVE-2021-0001", "dep-f1")
    followup = _make_report(_OTHER_PROJECT_ID, "scan-follow-1", [dep_f], [vuln_f])

    result = analyzer.analyze(baseline, followup)

    assert result.comparison_status == "MANUAL REVIEW REQUIRED"
    # No finding-level comparison performed across different projects
    assert result.findings == []
    assert result.baseline_scan_id == "scan-base-1"
    assert result.followup_scan_id == "scan-follow-1"


# ---------------------------------------------------------------------------
# Test 13 — dependency identity by package_name::ecosystem (not by row UUID)
# ---------------------------------------------------------------------------

def test_dependency_identity_by_package_name_ecosystem(analyzer):
    # Baseline dep UUID differs from follow-up dep UUID.
    # Matching must use (package_name, ecosystem), not the scan-scoped row ID.
    dep_b = _make_dep("uuid-baseline-dep-abc", "requests", "pypi", "2.25.0")
    vuln_b = _make_vuln("CVE-2022-0001", "uuid-baseline-dep-abc")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b])

    dep_f = _make_dep("uuid-followup-dep-xyz", "requests", "pypi", "2.28.2")
    vuln_f = _make_vuln("CVE-2022-0001", "uuid-followup-dep-xyz")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [vuln_f])

    result = analyzer.analyze(baseline, followup)

    assert result.comparison_status == "VERIFIED STILL PRESENT"
    assert len(result.findings) == 1

    f = result.findings[0]
    assert f.vulnerability_id == "CVE-2022-0001"
    # dependency_key uses package_name::ecosystem, not the internal row UUID
    assert f.dependency_key == "requests::pypi"
    assert f.baseline_version == "2.25.0"
    assert f.followup_version == "2.28.2"


# ---------------------------------------------------------------------------
# Test 14 — multiple vulnerabilities on the same dependency
# ---------------------------------------------------------------------------

def test_multiple_vulnerabilities_same_dependency(analyzer):
    dep_b = _make_dep("dep-b1", "log4j", "maven", "2.14.0")
    vuln_b1 = _make_vuln("CVE-2021-44228", "dep-b1")
    vuln_b2 = _make_vuln("CVE-2021-45046", "dep-b1")
    vuln_b3 = _make_vuln("CVE-2021-45105", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b1, vuln_b2, vuln_b3])

    dep_f = _make_dep("dep-f1", "log4j", "maven", "2.17.0")
    # Only CVE-44228 still present; other two remediated
    vuln_f1 = _make_vuln("CVE-2021-44228", "dep-f1")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [vuln_f1])

    result = analyzer.analyze(baseline, followup)

    assert result.comparison_status == "PARTIALLY REMEDIATED"
    assert len(result.findings) == 3

    statuses = {f.vulnerability_id: f.comparison_status for f in result.findings}
    assert statuses["CVE-2021-44228"] == "VERIFIED STILL PRESENT"
    assert statuses["CVE-2021-45046"] == "VERIFIED REMEDIATED"
    assert statuses["CVE-2021-45105"] == "VERIFIED REMEDIATED"

    for f in result.findings:
        assert f.dependency_key == "log4j::maven"


# ---------------------------------------------------------------------------
# Test 15 — multiple dependencies compared independently
# ---------------------------------------------------------------------------

def test_multiple_dependencies(analyzer):
    dep_b1 = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    dep_b2 = _make_dep("dep-b2", "lodash", "npm", "4.17.20")
    vuln_b1 = _make_vuln("CVE-2021-0001", "dep-b1")
    vuln_b2 = _make_vuln("CVE-2021-0002", "dep-b2")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b1, dep_b2], [vuln_b1, vuln_b2])

    dep_f1 = _make_dep("dep-f1", "axios", "npm", "1.0.0")
    dep_f2 = _make_dep("dep-f2", "lodash", "npm", "4.17.21")
    # axios CVE remediated; lodash CVE still present
    vuln_f2 = _make_vuln("CVE-2021-0002", "dep-f2")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f1, dep_f2], [vuln_f2])

    result = analyzer.analyze(baseline, followup)

    assert result.comparison_status == "PARTIALLY REMEDIATED"

    by_id = {f.vulnerability_id: f for f in result.findings}
    assert by_id["CVE-2021-0001"].comparison_status == "VERIFIED REMEDIATED"
    assert by_id["CVE-2021-0001"].dependency_key == "axios::npm"
    assert by_id["CVE-2021-0002"].comparison_status == "VERIFIED STILL PRESENT"
    assert by_id["CVE-2021-0002"].dependency_key == "lodash::npm"


# ---------------------------------------------------------------------------
# Test 16 — unchanged finding (same version, same finding)
# ---------------------------------------------------------------------------

def test_unchanged_finding(analyzer):
    dep_b = _make_dep("dep-b1", "requests", "pypi", "2.25.0")
    vuln_b = _make_vuln("CVE-2022-0001", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b])

    dep_f = _make_dep("dep-f1", "requests", "pypi", "2.25.0")
    vuln_f = _make_vuln("CVE-2022-0001", "dep-f1")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [vuln_f])

    result = analyzer.analyze(baseline, followup)

    assert result.comparison_status == "VERIFIED STILL PRESENT"
    f = result.findings[0]
    assert f.comparison_status == "VERIFIED STILL PRESENT"
    assert f.baseline_version == "2.25.0"
    assert f.followup_version == "2.25.0"
    # No version-change note when version is identical
    assert "Dependency version changed" not in (f.comparison_note or "")


# ---------------------------------------------------------------------------
# Test 17 — follow-up-only finding not marked as remediated
# ---------------------------------------------------------------------------

def test_followup_only_finding_not_marked_remediated(analyzer):
    # Baseline has CVE-A on axios
    dep_b1 = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    vuln_b1 = _make_vuln("CVE-2021-A", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b1], [vuln_b1])

    # Follow-up: CVE-A on axios (still present) + CVE-B on lodash (new, not in baseline)
    dep_f1 = _make_dep("dep-f1", "axios", "npm", "0.21.0")
    dep_f2 = _make_dep("dep-f2", "lodash", "npm", "4.17.20")
    vuln_f1 = _make_vuln("CVE-2021-A", "dep-f1")
    vuln_f2 = _make_vuln("CVE-2021-B", "dep-f2")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f1, dep_f2], [vuln_f1, vuln_f2])

    result = analyzer.analyze(baseline, followup)

    by_id = {f.vulnerability_id: f for f in result.findings}

    # CVE-A: present in both → VERIFIED STILL PRESENT
    assert by_id["CVE-2021-A"].comparison_status == "VERIFIED STILL PRESENT"

    # CVE-B: only in follow-up → must NOT be VERIFIED REMEDIATED
    assert by_id["CVE-2021-B"].comparison_status != "VERIFIED REMEDIATED"
    # It must be the conservative fallback
    assert by_id["CVE-2021-B"].comparison_status == "MANUAL REVIEW REQUIRED"
    assert by_id["CVE-2021-B"].baseline_version is None
    assert by_id["CVE-2021-B"].followup_version == "4.17.20"


# ---------------------------------------------------------------------------
# Test 18 — no causal language in comparison notes
# ---------------------------------------------------------------------------

def test_no_causal_language_in_note(analyzer):
    dep_b = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    vuln_b1 = _make_vuln("CVE-2021-0001", "dep-b1")
    vuln_b2 = _make_vuln("CVE-2021-0002", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b1, vuln_b2])

    dep_f = _make_dep("dep-f1", "axios", "npm", "2.0.0")
    vuln_f2 = _make_vuln("CVE-2021-0002", "dep-f1")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [vuln_f2])

    result = analyzer.analyze(baseline, followup)

    for f in result.findings:
        note_lower = (f.comparison_note or "").lower()
        for forbidden in _FORBIDDEN_CAUSAL_WORDS:
            assert forbidden.lower() not in note_lower, (
                f"Forbidden causal word {forbidden!r} found in note for "
                f"{f.vulnerability_id}: {f.comparison_note!r}"
            )


# ---------------------------------------------------------------------------
# Test 19 — no injection into follow-up snapshot
# ---------------------------------------------------------------------------

def test_no_injection_into_followup_snapshot(analyzer):
    dep_b = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    vuln_b = _make_vuln("CVE-2021-0001", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b])

    dep_f = _make_dep("dep-f1", "axios", "npm", "1.0.0")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [])

    # Snapshot of follow-up state before analysis
    followup_vuln_count_before = len(followup.vulnerabilities)
    followup_vuln_ids_before = [v.vulnerability_id for v in followup.vulnerabilities]

    _ = analyzer.analyze(baseline, followup)

    # Follow-up must remain exactly as supplied
    assert len(followup.vulnerabilities) == followup_vuln_count_before
    assert [v.vulnerability_id for v in followup.vulnerabilities] == followup_vuln_ids_before

    # Specifically: CVE-2021-0001 from baseline must NOT appear in follow-up
    followup_vuln_ids_after = [v.vulnerability_id for v in followup.vulnerabilities]
    assert "CVE-2021-0001" not in followup_vuln_ids_after


# ---------------------------------------------------------------------------
# Test 20 — original inputs not mutated
# ---------------------------------------------------------------------------

def test_original_inputs_not_mutated(analyzer):
    dep_b = _make_dep("dep-b1", "axios", "npm", "0.21.0")
    vuln_b1 = _make_vuln("CVE-2021-0001", "dep-b1")
    vuln_b2 = _make_vuln("CVE-2021-0002", "dep-b1")
    baseline = _make_report(_PROJECT_ID, "scan-base-1", [dep_b], [vuln_b1, vuln_b2])

    dep_f = _make_dep("dep-f1", "axios", "npm", "1.0.0")
    vuln_f = _make_vuln("CVE-2021-0002", "dep-f1")
    followup = _make_report(_PROJECT_ID, "scan-follow-1", [dep_f], [vuln_f])

    # Capture state before
    baseline_dep_count = len(baseline.dependencies)
    baseline_vuln_count = len(baseline.vulnerabilities)
    baseline_dep_ids = [d.id for d in baseline.dependencies]
    baseline_vuln_ids = [v.vulnerability_id for v in baseline.vulnerabilities]

    followup_dep_count = len(followup.dependencies)
    followup_vuln_count = len(followup.vulnerabilities)
    followup_dep_ids = [d.id for d in followup.dependencies]
    followup_vuln_ids = [v.vulnerability_id for v in followup.vulnerabilities]

    _ = analyzer.analyze(baseline, followup)

    # Assert baseline unchanged
    assert len(baseline.dependencies) == baseline_dep_count
    assert len(baseline.vulnerabilities) == baseline_vuln_count
    assert [d.id for d in baseline.dependencies] == baseline_dep_ids
    assert [v.vulnerability_id for v in baseline.vulnerabilities] == baseline_vuln_ids

    # Assert follow-up unchanged
    assert len(followup.dependencies) == followup_dep_count
    assert len(followup.vulnerabilities) == followup_vuln_count
    assert [d.id for d in followup.dependencies] == followup_dep_ids
    assert [v.vulnerability_id for v in followup.vulnerabilities] == followup_vuln_ids
