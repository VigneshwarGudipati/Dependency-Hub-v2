"""
Phase J focused tests — DependencyTreeAnalyzer.

Coverage map:
 1. Empty dependency graph
 2. One direct dependency (no edges)
 3. Direct + transitive (with edges)
 4. Multiple branches (fan-out from one root)
 5. Duplicate edge handling
 6. Cycle detection
 7. Orphan dependency
 8. Old snapshot without edges (backward compat)
 9. Unsupported ecosystem retained
10. Input immutability
11. Deterministic ordering
12. JSON report contains Dependency Tree Summary section
13. HTML report contains Dependency Tree Summary heading
14. PDF export does not crash
15. Software Inventory Metadata section present
16. No fabricated identifiers
17. Analyzer requires no DB session
18. Depth from edge data
19. Unknown depth fallback
20. Schema 1.0.0 backward compatibility
"""

import pytest

from app.services.reporting.report_data import (
    ReportData,
    ReportProjectData,
    ReportScanData,
    ReportSummaryData,
    ReportSeverityCounts,
    ReportDependencyData,
    ReportEdgeData,
    ReportVulnerabilityData,
)
from app.services.reporting.analyzer.dependency_tree_analyzer import (
    DependencyTreeAnalyzer,
    DependencyNode,
    DependencyTreeResult,
)

# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------

_PROJECT_ID = "project-j-1"
_SCAN_ID = "scan-j-1"


def _dep(
    dep_id: str,
    package_name: str,
    ecosystem: str = "npm",
    package_version: str = "1.0.0",
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
        registry_metadata=registry_metadata or {},
    )


def _edge(
    parent_id: str,
    child_id: str,
    relationship_type: str = "TRANSITIVE",
    depth: int = 1,
) -> ReportEdgeData:
    return ReportEdgeData(
        parent_id=parent_id,
        child_id=child_id,
        relationship_type=relationship_type,
        depth=depth,
    )


def _report(
    dependencies: list,
    edges: list = None,
    schema_version: str = "1.1.0",
    project_id: str = _PROJECT_ID,
    scan_id: str = _SCAN_ID,
) -> ReportData:
    return ReportData(
        metadata={
            "project_id": project_id,
            "scan_id": scan_id,
            "organization_id": "org-j-1",
            "schema_version": schema_version,
            "snapshot_sha256": "cafebabe",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
        project=ReportProjectData(id=project_id, name="Project J"),
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
        edges=edges or [],
    )


@pytest.fixture
def analyzer() -> DependencyTreeAnalyzer:
    return DependencyTreeAnalyzer()


# ---------------------------------------------------------------------------
# Test 1 — empty dependency graph
# ---------------------------------------------------------------------------

def test_empty_dependency_graph(analyzer):
    report = _report(dependencies=[], edges=[])

    result = analyzer.analyze(report)

    assert isinstance(result, DependencyTreeResult)
    assert result.total_dependencies == 0
    assert result.direct_count == 0
    assert result.non_direct_count == 0
    assert result.nodes == []
    assert result.cycle_detected is False
    assert result.orphan_count == 0


# ---------------------------------------------------------------------------
# Test 2 — one direct dependency, no edges
# ---------------------------------------------------------------------------

def test_one_direct_dependency_no_edges(analyzer):
    """Test 2: single direct dep, no edge data (schema 1.0.0 — old snapshot)."""
    dep = _dep("dep-1", "react", is_direct=True)
    report = _report([dep], edges=[], schema_version="1.0.0")

    result = analyzer.analyze(report)

    assert result.total_dependencies == 1
    assert result.direct_count == 1
    assert result.non_direct_count == 0
    assert result.edges_available is False
    node = result.nodes[0]
    assert node.dependency_id == "dep-1"
    assert node.depth == -1     # unknown — no edges
    assert node.parent_ids == []
    assert node.child_ids == []
    # Limitation text must mention edge data
    assert any("edge" in lim.lower() for lim in result.limitations)


# ---------------------------------------------------------------------------
# edges_available semantic — three explicit cases
# ---------------------------------------------------------------------------

def test_edges_available_false_for_schema_1_0_0(analyzer):
    """
    Case A: old snapshot schema 1.0.0 — 'edges' key was never serialized.
    edges_available must be False regardless of whether edges list is empty.
    """
    dep = _dep("dep-1", "react", is_direct=True)
    # _report() with schema_version="1.0.0" and empty edges simulates old snapshot
    report = _report([dep], edges=[], schema_version="1.0.0")

    result = analyzer.analyze(report)

    assert result.edges_available is False, (
        "Schema 1.0.0 snapshot must report edges_available=False "
        "(edge data was never serialized in this schema)"
    )
    assert any("1.0.0" in lim or "predates" in lim for lim in result.limitations)


def test_edges_available_true_for_schema_1_1_0_empty_edges(analyzer):
    """
    Case B: new snapshot schema 1.1.0 with edges=[].
    The 'edges' key was serialized; scanner ran but found 0 relationships.
    edges_available must be True (capability confirmed; count = 0).
    """
    dep = _dep("dep-1", "react", is_direct=True)
    report = _report([dep], edges=[], schema_version="1.1.0")

    result = analyzer.analyze(report)

    assert result.edges_available is True, (
        "Schema 1.1.0 snapshot must report edges_available=True "
        "even when edges=[] (edge capability was confirmed; 0 relationships recorded)"
    )
    # A limitation noting 0 relationships should be present
    assert any("0 relationships" in lim or "capability" in lim.lower() for lim in result.limitations)


def test_edges_available_true_for_schema_1_1_0_with_edges(analyzer):
    """
    Case C: new snapshot schema 1.1.0 with real edges.
    edges_available must be True.
    """
    root = _dep("dep-1", "react", is_direct=True)
    child = _dep("dep-2", "react-dom", is_direct=False)
    edge = _edge("dep-1", "dep-2")
    report = _report([root, child], edges=[edge], schema_version="1.1.0")

    result = analyzer.analyze(report)

    assert result.edges_available is True
    # No "unavailable" limitation — edges are present
    assert not any("predates" in lim for lim in result.limitations)


# ---------------------------------------------------------------------------
# Test 3 — direct + transitive with edges
# ---------------------------------------------------------------------------

def test_direct_plus_transitive(analyzer):
    root = _dep("dep-1", "react", is_direct=True)
    child = _dep("dep-2", "react-dom", is_direct=False)
    edge = _edge("dep-1", "dep-2", relationship_type="TRANSITIVE", depth=1)
    report = _report([root, child], edges=[edge])

    result = analyzer.analyze(report)

    assert result.edges_available is True
    assert result.total_dependencies == 2
    assert result.direct_count == 1
    assert result.non_direct_count == 1

    # Find nodes by ID
    root_node = next(n for n in result.nodes if n.dependency_id == "dep-1")
    child_node = next(n for n in result.nodes if n.dependency_id == "dep-2")

    assert root_node.depth == 0           # direct root
    assert root_node.child_ids == ["dep-2"]
    assert root_node.parent_ids == []

    assert child_node.depth == 1          # one hop from root
    assert child_node.parent_ids == ["dep-1"]
    assert child_node.child_ids == []
    assert child_node.relationship_type == "TRANSITIVE"


# ---------------------------------------------------------------------------
# Test 4 — multiple branches (fan-out from one root)
# ---------------------------------------------------------------------------

def test_multiple_branches(analyzer):
    root = _dep("dep-1", "webpack", is_direct=True)
    child_a = _dep("dep-2", "webpack-cli", is_direct=False)
    child_b = _dep("dep-3", "webpack-dev-server", is_direct=False)
    edges = [
        _edge("dep-1", "dep-2", depth=1),
        _edge("dep-1", "dep-3", depth=1),
    ]
    report = _report([root, child_a, child_b], edges=edges)

    result = analyzer.analyze(report)

    root_node = next(n for n in result.nodes if n.dependency_id == "dep-1")
    assert sorted(root_node.child_ids) == ["dep-2", "dep-3"]

    for cid in ["dep-2", "dep-3"]:
        node = next(n for n in result.nodes if n.dependency_id == cid)
        assert node.parent_ids == ["dep-1"]
        assert node.depth == 1


# ---------------------------------------------------------------------------
# Test 5 — duplicate edge handling
# ---------------------------------------------------------------------------

def test_duplicate_edge_handling(analyzer):
    root = _dep("dep-1", "react", is_direct=True)
    child = _dep("dep-2", "react-dom", is_direct=False)
    dup_edges = [
        _edge("dep-1", "dep-2", relationship_type="TRANSITIVE", depth=1),
        _edge("dep-1", "dep-2", relationship_type="TRANSITIVE", depth=1),  # duplicate
    ]
    report = _report([root, child], edges=dup_edges)

    result = analyzer.analyze(report)

    root_node = next(n for n in result.nodes if n.dependency_id == "dep-1")
    child_node = next(n for n in result.nodes if n.dependency_id == "dep-2")

    # Duplicate must not create duplicate entries
    assert root_node.child_ids.count("dep-2") == 1
    assert child_node.parent_ids.count("dep-1") == 1


# ---------------------------------------------------------------------------
# Test 6 — cycle detection
# ---------------------------------------------------------------------------

def test_cycle_detection(analyzer):
    dep_a = _dep("dep-1", "pkg-a", is_direct=True)
    dep_b = _dep("dep-2", "pkg-b", is_direct=False)
    cyclic_edges = [
        _edge("dep-1", "dep-2"),
        _edge("dep-2", "dep-1"),  # back-edge → cycle
    ]
    report = _report([dep_a, dep_b], edges=cyclic_edges)

    result = analyzer.analyze(report)

    assert result.cycle_detected is True
    # Analyzer must not hang or raise — it must return a valid result
    assert isinstance(result, DependencyTreeResult)
    assert result.total_dependencies == 2
    # Cycle must be noted in limitations
    assert any("cycle" in lim.lower() for lim in result.limitations)


# ---------------------------------------------------------------------------
# Test 7 — orphan dependency
# ---------------------------------------------------------------------------

def test_orphan_dependency(analyzer):
    root = _dep("dep-1", "react", is_direct=True)
    orphan = _dep("dep-2", "orphaned-lib", is_direct=False)
    # Edge only from root; orphan has no edges at all
    edges = [_edge("dep-1", "dep-3", depth=1)]  # dep-3 doesn't exist → dangling
    report = _report([root, orphan], edges=edges)

    result = analyzer.analyze(report)

    # orphan = non-direct dep with no parent_ids and no child_ids
    orphan_node = next(n for n in result.nodes if n.dependency_id == "dep-2")
    assert orphan_node.parent_ids == []
    assert orphan_node.child_ids == []
    assert result.orphan_count >= 1

    # Dangling edge should be noted in limitations
    assert any("dangling" in lim.lower() or "ignored" in lim.lower() for lim in result.limitations)


# ---------------------------------------------------------------------------
# Test 8 — old snapshot without edges (backward compatibility)
# ---------------------------------------------------------------------------

def test_old_snapshot_without_edges_no_edges_field(analyzer):
    """ReportData constructed without edges (as if loaded from 1.0.0 snapshot)."""
    dep = _dep("dep-1", "flask", ecosystem="pypi", is_direct=True)
    # Construct manually with no edges field
    report = ReportData(
        metadata={
            "project_id": _PROJECT_ID,
            "scan_id": _SCAN_ID,
            "schema_version": "1.0.0",
            "snapshot_sha256": "abc",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
        project=ReportProjectData(id=_PROJECT_ID, name="P"),
        scan=ReportScanData(id=_SCAN_ID, scan_type="FULL", started_at=None,
                            completed_at=None, scanner_version="1.0.0"),
        summary=ReportSummaryData(
            total_packages=1, vulnerable_packages=0,
            vulnerability_findings=0, severity_counts=ReportSeverityCounts(),
        ),
        dependencies=[dep],
        vulnerabilities=[],
        # edges defaults to []
    )

    result = analyzer.analyze(report)

    assert result.edges_available is False
    assert result.total_dependencies == 1
    assert result.nodes[0].dependency_id == "dep-1"
    assert result.nodes[0].depth == -1


# ---------------------------------------------------------------------------
# Test 9 — unsupported ecosystem retained
# ---------------------------------------------------------------------------

def test_unsupported_ecosystem_retained(analyzer):
    maven_dep = _dep("dep-1", "log4j", ecosystem="maven", is_direct=True)
    cargo_dep = _dep("dep-2", "serde", ecosystem="cargo", is_direct=False)
    report = _report([maven_dep, cargo_dep], edges=[_edge("dep-1", "dep-2")])

    result = analyzer.analyze(report)

    ecosystems = {n.ecosystem for n in result.nodes}
    assert "maven" in ecosystems
    assert "cargo" in ecosystems
    assert result.total_dependencies == 2


# ---------------------------------------------------------------------------
# Test 10 — input immutability
# ---------------------------------------------------------------------------

def test_input_immutability(analyzer):
    root = _dep("dep-1", "react", is_direct=True,
                registry_metadata={"license": "MIT", "outdated": False})
    child = _dep("dep-2", "react-dom", is_direct=False)
    edge = _edge("dep-1", "dep-2")
    report = _report([root, child], edges=[edge])

    dep_ids_before = [d.id for d in report.dependencies]
    edges_before = [(e.parent_id, e.child_id) for e in report.edges]
    reg_meta_before = dict(report.dependencies[0].registry_metadata)

    _ = analyzer.analyze(report)

    assert [d.id for d in report.dependencies] == dep_ids_before
    assert [(e.parent_id, e.child_id) for e in report.edges] == edges_before
    assert dict(report.dependencies[0].registry_metadata) == reg_meta_before


# ---------------------------------------------------------------------------
# Test 11 — deterministic ordering
# ---------------------------------------------------------------------------

def test_deterministic_ordering(analyzer):
    deps = [
        _dep("dep-3", "zlib", ecosystem="npm", is_direct=False),
        _dep("dep-1", "axios", ecosystem="npm", is_direct=True),
        _dep("dep-2", "lodash", ecosystem="npm", is_direct=False),
    ]
    report = _report(deps, edges=[])

    result_a = analyzer.analyze(report)
    result_b = analyzer.analyze(report)

    assert [n.dependency_id for n in result_a.nodes] == [n.dependency_id for n in result_b.nodes]


# ---------------------------------------------------------------------------
# Test 12 — JSON report contains Dependency Tree Summary section
# ---------------------------------------------------------------------------

def test_json_report_contains_tree_section():
    import json
    from app.services.reporting.report_document import ReportDocument
    from app.services.reporting.exporters.json import JsonExporter

    report = _report([_dep("dep-1", "react", is_direct=True)], edges=[])
    doc = ReportDocument.from_report_data(report)
    raw = JsonExporter().export(doc)
    data = json.loads(raw)

    section_titles = [s["title"] for s in data["sections"]]
    assert "Dependency Tree Summary" in section_titles


# ---------------------------------------------------------------------------
# Test 13 — HTML report contains Dependency Tree Summary heading
# ---------------------------------------------------------------------------

def test_html_report_contains_tree_section():
    from app.services.reporting.report_document import ReportDocument
    from app.services.reporting.exporters.html import HtmlExporter

    report = _report([_dep("dep-1", "react", is_direct=True)], edges=[])
    doc = ReportDocument.from_report_data(report)
    html = HtmlExporter().export(doc).decode("utf-8")

    assert "Dependency Tree Summary" in html


# ---------------------------------------------------------------------------
# Test 14 — PDF export does not crash
# ---------------------------------------------------------------------------

def test_pdf_export_does_not_crash():
    from app.services.reporting.report_document import ReportDocument
    from app.services.reporting.exporters.pdf import PdfExporter

    report = _report([_dep("dep-1", "react", is_direct=True)], edges=[])
    doc = ReportDocument.from_report_data(report)
    pdf_bytes = PdfExporter().export(doc)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0


# ---------------------------------------------------------------------------
# Test 15 — Software Inventory Metadata section present
# ---------------------------------------------------------------------------

def test_software_inventory_metadata_section_present():
    import json
    from app.services.reporting.report_document import ReportDocument
    from app.services.reporting.exporters.json import JsonExporter

    report = _report([_dep("dep-1", "react", is_direct=True)], edges=[])
    doc = ReportDocument.from_report_data(report)
    raw = JsonExporter().export(doc)
    data = json.loads(raw)

    section_titles = [s["title"] for s in data["sections"]]
    assert "Software Inventory Metadata" in section_titles

    sbom_section = next(s for s in data["sections"] if s["title"] == "Software Inventory Metadata")
    content = sbom_section["content"]

    # Must explicitly state no standards-compliant SBOM was generated
    assert "CycloneDX" in content or "SPDX" in content
    assert "No standards-compliant" in content or "no standards-compliant" in content.lower()

    # Must not claim compliance
    for phrase in ("compliant SBOM is generated", "standards compliant", "approved", "legally safe"):
        assert phrase.lower() not in content.lower() or "No" in content.split(phrase.lower())[0][-5:]


# ---------------------------------------------------------------------------
# Test 16 — no fabricated identifiers
# ---------------------------------------------------------------------------

def test_no_fabricated_identifiers(analyzer):
    dep = _dep("uuid-exact-id-xyz", "react", is_direct=True)
    report = _report([dep], edges=[])

    result = analyzer.analyze(report)

    # dependency_id must be the exact snapshot value, nothing computed
    assert result.nodes[0].dependency_id == "uuid-exact-id-xyz"
    # package_name must be unchanged
    assert result.nodes[0].package_name == "react"


# ---------------------------------------------------------------------------
# Test 17 — analyzer requires no DB session
# ---------------------------------------------------------------------------

def test_analyzer_requires_no_db(analyzer):
    """Analyzer completes without a DB session argument."""
    dep = _dep("dep-1", "flask", ecosystem="pypi", is_direct=True)
    report = _report([dep], edges=[])

    # analyze() takes only report_data — no session parameter
    result = analyzer.analyze(report)
    assert result.total_dependencies == 1


# ---------------------------------------------------------------------------
# Test 18 — depth from edge data
# ---------------------------------------------------------------------------

def test_depth_from_edge_data(analyzer):
    root = _dep("dep-1", "root-pkg", is_direct=True)
    level1 = _dep("dep-2", "level1-pkg", is_direct=False)
    level2 = _dep("dep-3", "level2-pkg", is_direct=False)
    edges = [
        _edge("dep-1", "dep-2", depth=1),
        _edge("dep-2", "dep-3", depth=2),
    ]
    report = _report([root, level1, level2], edges=edges)

    result = analyzer.analyze(report)

    n1 = next(n for n in result.nodes if n.dependency_id == "dep-1")
    n2 = next(n for n in result.nodes if n.dependency_id == "dep-2")
    n3 = next(n for n in result.nodes if n.dependency_id == "dep-3")

    assert n1.depth == 0   # direct root
    assert n2.depth == 1   # one hop from root
    assert n3.depth == 2   # two hops from root


# ---------------------------------------------------------------------------
# Test 19 — unknown depth fallback
# ---------------------------------------------------------------------------

def test_unknown_depth_fallback_no_edges(analyzer):
    dep = _dep("dep-1", "react", is_direct=False)
    report = _report([dep], edges=[])

    result = analyzer.analyze(report)

    assert result.nodes[0].depth == -1


def test_unknown_depth_fallback_unreachable_node(analyzer):
    """A non-direct dep with no edges to it stays at depth -1."""
    root = _dep("dep-1", "root", is_direct=True)
    isolated = _dep("dep-2", "orphan", is_direct=False)
    # No edge connecting dep-2 to any node
    report = _report([root, isolated], edges=[_edge("dep-1", "dep-1")])
    # Self-loop edge is a cycle, but dep-2 remains unreachable

    result = analyzer.analyze(report)

    orphan_node = next(n for n in result.nodes if n.dependency_id == "dep-2")
    assert orphan_node.depth == -1


# ---------------------------------------------------------------------------
# Test 20 — schema 1.0.0 backward compatibility via from_snapshot
# ---------------------------------------------------------------------------

def test_schema_1_0_0_backward_compat_from_snapshot():
    """
    Snapshot without 'edges' key must parse successfully with
    edges defaulting to []. from_snapshot must accept schema 1.0.0.
    """
    snapshot = {
        "metadata": {
            "project_id": _PROJECT_ID,
            "scan_id": _SCAN_ID,
            "organization_id": "org-1",
            "schema_version": "1.0.0",    # old schema — no edges
            "snapshot_sha256": "oldsha",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
        "canonical_payload": {
            "project": {"id": _PROJECT_ID, "name": "Old Project"},
            "scan": {
                "id": _SCAN_ID,
                "scan_type": "FULL",
                "scanner_version": "0.9.0",
                "started_at": None,
                "completed_at": None,
            },
            "summary": {
                "total_packages": 1,
                "vulnerable_packages": 0,
                "vulnerability_findings": 0,
                "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            },
            "dependencies": [
                {
                    "id": "dep-old-1",
                    "package_name": "requests",
                    "ecosystem": "pypi",
                    "package_version": "2.28.0",
                    "dependency_type": "RUNTIME",
                    "is_direct": True,
                    "registry_metadata": {},
                }
            ],
            "vulnerabilities": [],
            # No "edges" key at all
        },
    }

    report = ReportData.from_snapshot(snapshot)
    assert report.edges == []

    analyzer = DependencyTreeAnalyzer()
    result = analyzer.analyze(report)

    assert result.edges_available is False
    assert result.total_dependencies == 1
    assert result.nodes[0].dependency_id == "dep-old-1"
    # Limitation must be present
    assert any("edge" in lim.lower() for lim in result.limitations)


# ---------------------------------------------------------------------------
# Test — inventory count arithmetic (bonus — DependencyTreeResult)
# ---------------------------------------------------------------------------

def test_count_arithmetic(analyzer):
    deps = [
        _dep("dep-1", "react", is_direct=True),
        _dep("dep-2", "lodash", is_direct=True),
        _dep("dep-3", "axios", is_direct=False),
        _dep("dep-4", "zlib", is_direct=False),
    ]
    report = _report(deps, edges=[])

    result = analyzer.analyze(report)

    assert result.direct_count == 2
    assert result.non_direct_count == 2
    assert result.direct_count + result.non_direct_count == result.total_dependencies
