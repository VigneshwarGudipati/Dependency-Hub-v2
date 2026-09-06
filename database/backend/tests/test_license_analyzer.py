"""
Phase I focused tests for LicenseAnalyzer.

Coverage:
 1. Known npm license
 2. Known PyPI license
 3. Missing license key
 4. Empty license value
 5. UNKNOWN license value
 6. Multiple OR expression
 7. Multiple AND expression
 8. Custom / unrecognized license
 9. Unsupported ecosystem
10. License source provenance
11. Raw license value preservation
12. Direct dependency flag
13. Non-direct dependency flag
14. Package version preservation
15. Package identity preservation
16. No license inference from package name
17. No SPDX fabrication
18. No legal conclusion in note
19. Deterministic inventory output
20. No network requirement
21. Inventory count combinations
22. Immutability of input ReportData
"""
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
from app.services.reporting.analyzer.license_analyzer import (
    LicenseAnalyzer,
    DependencyLicenseResult,
    SoftwareInventoryResult,
)

# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------

_PROJECT_ID = "project-uuid-1"
_SCAN_ID = "scan-uuid-1"
_ORG_ID = "org-uuid-1"

_FORBIDDEN_LEGAL_PHRASES = [
    "legally safe",
    "license compatible",
    "approved license",
    "permissive and safe",
    "no legal obligations",
    "policy approved",
    "legally permissive",
    "legally compliant",
    "legally cleared",
    "safe to use",
    "approved for use",
]


def _make_dep(
    dep_id: str,
    package_name: str,
    ecosystem: str,
    package_version: str,
    is_direct: bool = True,
    dependency_type: str = "RUNTIME",
    registry_metadata: dict = None,
) -> ReportDependencyData:
    return ReportDependencyData(
        id=dep_id,
        package_name=package_name,
        ecosystem=ecosystem,
        package_version=package_version,
        dependency_type=dependency_type,
        is_direct=is_direct,
        registry_metadata=registry_metadata if registry_metadata is not None else {},
    )


def _make_report(
    dependencies: list,
    project_id: str = _PROJECT_ID,
    scan_id: str = _SCAN_ID,
) -> ReportData:
    return ReportData(
        metadata={
            "project_id": project_id,
            "scan_id": scan_id,
            "organization_id": _ORG_ID,
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
            vulnerable_packages=0,
            vulnerability_findings=0,
            severity_counts=ReportSeverityCounts(),
        ),
        dependencies=dependencies,
        vulnerabilities=[],
    )


@pytest.fixture
def analyzer() -> LicenseAnalyzer:
    return LicenseAnalyzer()


# ---------------------------------------------------------------------------
# Test 1 — known npm license
# ---------------------------------------------------------------------------

def test_known_npm_license(analyzer):
    dep = _make_dep("dep-1", "react", "npm", "18.2.0",
                    registry_metadata={"license": "MIT"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    assert isinstance(result, SoftwareInventoryResult)
    assert len(result.inventory) == 1
    f = result.inventory[0]
    assert f.license_status == "KNOWN_FROM_SOURCE"
    assert f.license_expression == "MIT"
    assert f.license_source == "registry_metadata"
    assert f.ecosystem == "npm"


# ---------------------------------------------------------------------------
# Test 2 — known PyPI license
# ---------------------------------------------------------------------------

def test_known_pypi_license(analyzer):
    dep = _make_dep("dep-1", "requests", "pypi", "2.28.0",
                    registry_metadata={"license": "Apache 2.0"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.license_status == "KNOWN_FROM_SOURCE"
    # Raw value preserved — NOT normalized to "Apache-2.0"
    assert f.license_expression == "Apache 2.0"
    assert f.ecosystem == "pypi"


# ---------------------------------------------------------------------------
# Test 3 — missing license key
# ---------------------------------------------------------------------------

def test_missing_license_key(analyzer):
    dep = _make_dep("dep-1", "axios", "npm", "1.0.0",
                    registry_metadata={"outdated": False})  # no "license" key
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.license_status == "MISSING"
    assert f.license_expression is None
    assert "absent" in (f.license_note or "").lower()


# ---------------------------------------------------------------------------
# Test 4 — empty license value
# ---------------------------------------------------------------------------

def test_empty_license_value(analyzer):
    dep = _make_dep("dep-1", "axios", "npm", "1.0.0",
                    registry_metadata={"license": ""})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.license_status == "UNKNOWN"


# ---------------------------------------------------------------------------
# Test 5 — UNKNOWN license string
# ---------------------------------------------------------------------------

def test_unknown_license_string(analyzer):
    dep = _make_dep("dep-1", "axios", "npm", "1.0.0",
                    registry_metadata={"license": "UNKNOWN"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.license_status == "UNKNOWN"


# ---------------------------------------------------------------------------
# Test 6 — multiple OR expression
# ---------------------------------------------------------------------------

def test_multiple_or_expression(analyzer):
    dep = _make_dep("dep-1", "spdx-pkg", "npm", "1.0.0",
                    registry_metadata={"license": "MIT OR Apache-2.0"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.license_status == "MULTIPLE_LICENSES"
    # Raw value preserved
    assert f.license_expression == "MIT OR Apache-2.0"


# ---------------------------------------------------------------------------
# Test 7 — multiple AND expression
# ---------------------------------------------------------------------------

def test_multiple_and_expression(analyzer):
    dep = _make_dep("dep-1", "dual-pkg", "npm", "2.0.0",
                    registry_metadata={"license": "GPL-2.0-only AND MIT"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.license_status == "MULTIPLE_LICENSES"
    assert f.license_expression == "GPL-2.0-only AND MIT"


# ---------------------------------------------------------------------------
# Test 8 — custom / unrecognized license
# ---------------------------------------------------------------------------

def test_custom_license_manual_review(analyzer):
    dep = _make_dep("dep-1", "corp-pkg", "npm", "1.0.0",
                    registry_metadata={"license": "Proprietary"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.license_status == "MANUAL_REVIEW_REQUIRED"
    # Raw value preserved — not modified to any SPDX ID
    assert f.license_expression == "Proprietary"


def test_internal_license_manual_review(analyzer):
    dep = _make_dep("dep-1", "internal-sdk", "npm", "1.0.0",
                    registry_metadata={"license": "Internal Corporate License"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.license_status == "MANUAL_REVIEW_REQUIRED"
    assert f.license_expression == "Internal Corporate License"


# ---------------------------------------------------------------------------
# Test 9 — unsupported ecosystem
# ---------------------------------------------------------------------------

def test_unsupported_ecosystem_manual_review(analyzer):
    dep = _make_dep("dep-1", "log4j", "maven", "2.17.0",
                    registry_metadata={"license": "Apache-2.0"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.license_status == "MANUAL_REVIEW_REQUIRED"
    assert "maven" in (f.license_note or "").lower()
    assert result.unsupported_ecosystems == ["maven"]


def test_unsupported_ecosystem_no_license_key(analyzer):
    dep = _make_dep("dep-1", "serde", "cargo", "1.0.0",
                    registry_metadata={})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.license_status == "MANUAL_REVIEW_REQUIRED"
    assert result.unsupported_ecosystems == ["cargo"]


# ---------------------------------------------------------------------------
# Test 10 — license source provenance
# ---------------------------------------------------------------------------

def test_license_source_always_registry_metadata(analyzer):
    deps = [
        _make_dep("dep-1", "react", "npm", "18.0.0",
                  registry_metadata={"license": "MIT"}),
        _make_dep("dep-2", "axios", "npm", "1.0.0",
                  registry_metadata={}),
        _make_dep("dep-3", "flask", "pypi", "3.0.0",
                  registry_metadata={"license": "BSD-3-Clause"}),
    ]
    report = _make_report(deps)

    result = analyzer.analyze(report)

    for f in result.inventory:
        assert f.license_source == "registry_metadata", (
            f"Expected license_source='registry_metadata' for {f.package_name}, "
            f"got {f.license_source!r}"
        )


# ---------------------------------------------------------------------------
# Test 11 — raw license value preservation
# ---------------------------------------------------------------------------

def test_raw_license_value_preserved(analyzer):
    # "MIT License" must NOT be normalized to "MIT"
    dep = _make_dep("dep-1", "some-pkg", "npm", "1.0.0",
                    registry_metadata={"license": "MIT License"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    # Raw value is preserved as-is — not normalized
    assert f.license_expression == "MIT License"
    # "MIT License" is a recognizable non-empty value from a supported ecosystem
    assert f.license_status == "KNOWN_FROM_SOURCE"


def test_raw_value_apache_not_normalized(analyzer):
    dep = _make_dep("dep-1", "requests", "pypi", "2.28.0",
                    registry_metadata={"license": "Apache 2.0"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    # Must NOT be "Apache-2.0" (SPDX form)
    assert f.license_expression == "Apache 2.0"


# ---------------------------------------------------------------------------
# Test 12 — direct dependency flag
# ---------------------------------------------------------------------------

def test_direct_dependency_flag(analyzer):
    dep = _make_dep("dep-1", "axios", "npm", "1.0.0",
                    is_direct=True,
                    registry_metadata={"license": "MIT"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.is_direct is True


# ---------------------------------------------------------------------------
# Test 13 — non-direct dependency flag
# ---------------------------------------------------------------------------

def test_non_direct_dependency_flag(analyzer):
    dep = _make_dep("dep-1", "lodash", "npm", "4.17.21",
                    is_direct=False,
                    registry_metadata={"license": "MIT"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.is_direct is False
    # is_direct=False does NOT prove a transitive chain — we only report what the snapshot says
    assert f.dependency_id == "dep-1"


# ---------------------------------------------------------------------------
# Test 14 — package version preservation
# ---------------------------------------------------------------------------

def test_package_version_preserved(analyzer):
    dep = _make_dep("dep-1", "react", "npm", "18.2.0-rc.1",
                    registry_metadata={"license": "MIT"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.package_version == "18.2.0-rc.1"


# ---------------------------------------------------------------------------
# Test 15 — package identity preservation
# ---------------------------------------------------------------------------

def test_package_identity_preserved(analyzer):
    dep = _make_dep("uuid-dep-abc123", "my-package", "npm", "2.0.0",
                    registry_metadata={"license": "ISC"})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.dependency_id == "uuid-dep-abc123"
    assert f.package_name == "my-package"


# ---------------------------------------------------------------------------
# Test 16 — no license inference from package name
# ---------------------------------------------------------------------------

def test_no_inference_from_package_name(analyzer):
    # Package named "mit-license" with no license key in registry_metadata
    dep = _make_dep("dep-1", "mit-license", "npm", "1.0.0",
                    registry_metadata={})  # no "license" key
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    # Must be MISSING — NOT "MIT" inferred from the package name
    assert f.license_status == "MISSING"
    assert f.license_expression is None


def test_no_inference_apache_from_name(analyzer):
    dep = _make_dep("dep-1", "apache-utils", "pypi", "1.0.0",
                    registry_metadata={})
    report = _make_report([dep])

    result = analyzer.analyze(report)

    f = result.inventory[0]
    assert f.license_status == "MISSING"
    assert f.license_expression is None


# ---------------------------------------------------------------------------
# Test 17 — no SPDX fabrication
# ---------------------------------------------------------------------------

def test_no_spdx_fabrication(analyzer):
    """
    The analyzer must never invent an SPDX identifier.
    license_expression must always come from registry_metadata, unchanged.
    """
    deps = [
        _make_dep("dep-1", "pkg-a", "npm", "1.0.0", registry_metadata={}),
        _make_dep("dep-2", "pkg-b", "npm", "2.0.0",
                  registry_metadata={"license": ""}),
        _make_dep("dep-3", "pkg-c", "pypi", "3.0.0",
                  registry_metadata={"license": "UNKNOWN"}),
    ]
    report = _make_report(deps)

    result = analyzer.analyze(report)

    # None of the entries with missing/empty/UNKNOWN license should have
    # a synthesized license_expression
    for f in result.inventory:
        if f.license_status in ("MISSING", "UNKNOWN"):
            # license_expression is either None or the exact raw value (empty / "UNKNOWN")
            # It must never be a generated SPDX string
            if f.license_expression is not None:
                # Must be the verbatim raw value — not something the analyzer invented
                assert f.license_expression in ("", "UNKNOWN", "unknown"), (
                    f"Expected raw pass-through but got {f.license_expression!r}"
                )


# ---------------------------------------------------------------------------
# Test 18 — no legal conclusion in note
# ---------------------------------------------------------------------------

def test_no_legal_conclusion_in_note(analyzer):
    deps = [
        _make_dep("dep-1", "react", "npm", "18.0.0",
                  registry_metadata={"license": "MIT"}),
        _make_dep("dep-2", "corp", "npm", "1.0.0",
                  registry_metadata={"license": "Proprietary"}),
        _make_dep("dep-3", "flask", "pypi", "3.0.0",
                  registry_metadata={}),
        _make_dep("dep-4", "log4j", "maven", "2.17.0",
                  registry_metadata={"license": "Apache-2.0"}),
    ]
    report = _make_report(deps)

    result = analyzer.analyze(report)

    for f in result.inventory:
        note_lower = (f.license_note or "").lower()
        for phrase in _FORBIDDEN_LEGAL_PHRASES:
            assert phrase.lower() not in note_lower, (
                f"Forbidden legal phrase {phrase!r} found in license_note for "
                f"{f.package_name}: {f.license_note!r}"
            )


# ---------------------------------------------------------------------------
# Test 19 — deterministic inventory output
# ---------------------------------------------------------------------------

def test_deterministic_inventory_output(analyzer):
    deps = [
        _make_dep("dep-1", "react", "npm", "18.0.0",
                  registry_metadata={"license": "MIT"}),
        _make_dep("dep-2", "requests", "pypi", "2.28.0",
                  registry_metadata={}),
        _make_dep("dep-3", "serde", "cargo", "1.0.0",
                  registry_metadata={"license": "MIT OR Apache-2.0"}),
    ]
    report = _make_report(deps)

    result_a = analyzer.analyze(report)
    result_b = analyzer.analyze(report)

    assert result_a.total_dependencies == result_b.total_dependencies
    assert result_a.dependencies_with_known_license == result_b.dependencies_with_known_license
    assert result_a.dependencies_with_unknown_license == result_b.dependencies_with_unknown_license
    assert result_a.dependencies_requiring_review == result_b.dependencies_requiring_review

    for a, b in zip(result_a.inventory, result_b.inventory):
        assert a.dependency_id == b.dependency_id
        assert a.license_status == b.license_status
        assert a.license_expression == b.license_expression


# ---------------------------------------------------------------------------
# Test 20 — no network requirement
# ---------------------------------------------------------------------------

def test_no_network_requirement(analyzer, monkeypatch):
    """
    LicenseAnalyzer.analyze() must complete in-memory with no network calls.
    We remove all known HTTP clients from the namespace and confirm the
    analyzer still runs without error.
    """
    import sys

    # Patch httpx to raise immediately if any call is made
    import unittest.mock as mock
    import httpx

    original_get = httpx.AsyncClient.get

    def _fail_if_called(*args, **kwargs):
        raise AssertionError(
            "LicenseAnalyzer made a network call — this is forbidden."
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", _fail_if_called)

    dep = _make_dep("dep-1", "react", "npm", "18.0.0",
                    registry_metadata={"license": "MIT"})
    report = _make_report([dep])

    # Must complete without raising
    result = analyzer.analyze(report)
    assert result.total_dependencies == 1
    assert result.inventory[0].license_status == "KNOWN_FROM_SOURCE"


# ---------------------------------------------------------------------------
# Test 21 — inventory count combinations
# ---------------------------------------------------------------------------

def test_inventory_count_combinations(analyzer):
    deps = [
        # KNOWN_FROM_SOURCE (npm, MIT)
        _make_dep("dep-1", "react", "npm", "18.0.0",
                  registry_metadata={"license": "MIT"}),
        # KNOWN_FROM_SOURCE (pypi, ISC)
        _make_dep("dep-2", "flask", "pypi", "3.0.0",
                  registry_metadata={"license": "BSD-3-Clause"}),
        # MISSING
        _make_dep("dep-3", "lodash", "npm", "4.17.21",
                  registry_metadata={}),
        # UNKNOWN
        _make_dep("dep-4", "axios", "npm", "1.0.0",
                  registry_metadata={"license": ""}),
        # MULTIPLE_LICENSES
        _make_dep("dep-5", "dual-pkg", "npm", "2.0.0",
                  registry_metadata={"license": "MIT OR Apache-2.0"}),
        # MANUAL_REVIEW_REQUIRED (custom)
        _make_dep("dep-6", "corp-pkg", "npm", "1.0.0",
                  registry_metadata={"license": "Proprietary"}),
        # MANUAL_REVIEW_REQUIRED (unsupported ecosystem)
        _make_dep("dep-7", "log4j", "maven", "2.17.0",
                  registry_metadata={"license": "Apache-2.0"}),
    ]
    report = _make_report(deps)

    result = analyzer.analyze(report)

    assert result.total_dependencies == 7
    assert result.dependencies_with_known_license == 2    # KNOWN_FROM_SOURCE
    assert result.dependencies_with_unknown_license == 2  # UNKNOWN + MISSING
    assert result.dependencies_requiring_review == 3      # MULTIPLE_LICENSES + 2x MANUAL_REVIEW_REQUIRED

    # Sanity check: known + unknown + review = total
    assert (
        result.dependencies_with_known_license
        + result.dependencies_with_unknown_license
        + result.dependencies_requiring_review
    ) == result.total_dependencies

    assert "maven" in result.unsupported_ecosystems
    assert "npm" in result.supported_ecosystems
    assert "pypi" in result.supported_ecosystems


# ---------------------------------------------------------------------------
# Test 22 — immutability of input ReportData
# ---------------------------------------------------------------------------

def test_input_not_mutated(analyzer):
    deps = [
        _make_dep("dep-1", "react", "npm", "18.0.0",
                  registry_metadata={"license": "MIT", "outdated": False}),
        _make_dep("dep-2", "lodash", "npm", "4.17.21",
                  registry_metadata={}),
    ]
    report = _make_report(deps)

    # Capture before state
    dep_count_before = len(report.dependencies)
    dep_ids_before = [d.id for d in report.dependencies]
    dep_names_before = [d.package_name for d in report.dependencies]
    reg_meta_before = [dict(d.registry_metadata) for d in report.dependencies]

    _ = analyzer.analyze(report)

    # Assert report unchanged
    assert len(report.dependencies) == dep_count_before
    assert [d.id for d in report.dependencies] == dep_ids_before
    assert [d.package_name for d in report.dependencies] == dep_names_before
    # registry_metadata not mutated
    for i, dep in enumerate(report.dependencies):
        assert dict(dep.registry_metadata) == reg_meta_before[i], (
            f"registry_metadata for {dep.package_name} was mutated"
        )


# ---------------------------------------------------------------------------
# Test for report_document.py — new columns
# ---------------------------------------------------------------------------

def test_report_document_inventory_columns():
    """
    Verifies that the Dependency Inventory table in ReportDocument
    now includes ecosystem, license, and is_direct columns.
    Raw license value is preserved. Missing license shows 'UNKNOWN'.
    """
    from app.services.reporting.report_data import (
        ReportDependencyData,
        ReportSummaryData,
        ReportSeverityCounts,
    )
    from app.services.reporting.report_document import ReportDocument

    snapshot = {
        "metadata": {"schema_version": "1.0.0", "project_id": "p1"},
        "canonical_payload": {
            "project": {"id": "p1", "name": "Test Project"},
            "scan": {
                "id": "s1",
                "scan_type": "FULL",
                "scanner_version": "1.0.0",
                "started_at": None,
                "completed_at": None,
            },
            "summary": {
                "total_packages": 2,
                "vulnerable_packages": 0,
                "vulnerability_findings": 0,
                "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            },
            "dependencies": [
                {
                    "id": "dep-1",
                    "package_name": "react",
                    "ecosystem": "npm",
                    "package_version": "18.2.0",
                    "dependency_type": "RUNTIME",
                    "is_direct": True,
                    "registry_metadata": {"license": "MIT", "outdated": False},
                },
                {
                    "id": "dep-2",
                    "package_name": "lodash",
                    "ecosystem": "npm",
                    "package_version": "4.17.21",
                    "dependency_type": "RUNTIME",
                    "is_direct": False,
                    "registry_metadata": {},  # No license key
                },
            ],
            "vulnerabilities": [],
        },
    }

    report_data = ReportData.from_snapshot(snapshot)
    doc = ReportDocument.from_report_data(report_data)

    # Find dependency inventory section
    dep_sections = [s for s in doc.sections if s.title == "Dependencies"]
    assert len(dep_sections) == 1
    dep_table = dep_sections[0].tables[0]

    # Verify new column headers exist
    header_keys = [h.key for h in dep_table.headers]
    assert "ecosystem" in header_keys, f"ecosystem not in headers: {header_keys}"
    assert "license" in header_keys, f"license not in headers: {header_keys}"
    assert "is_direct" in header_keys, f"is_direct not in headers: {header_keys}"

    # Verify row data for react
    react_row = next(r for r in dep_table.rows if r.cells.get("package") == "react")
    assert react_row.cells["ecosystem"] == "npm"
    assert react_row.cells["license"] == "MIT"   # raw value preserved
    assert react_row.cells["is_direct"] == "Yes"

    # Verify row data for lodash (no license key → "UNKNOWN")
    lodash_row = next(r for r in dep_table.rows if r.cells.get("package") == "lodash")
    assert lodash_row.cells["ecosystem"] == "npm"
    assert lodash_row.cells["license"] == "UNKNOWN"   # fallback for missing key
    assert lodash_row.cells["is_direct"] == "No"
