"""
Phase J — DependencyTreeAnalyzer

Read-only, offline, deterministic analyzer over ReportData.edges and
ReportData.dependencies. Builds a dependency relationship graph (when edge
data is available in the snapshot) and produces DependencyTreeResult.

Guarantees
----------
- Input ReportData is never mutated.
- No network calls, no DB queries, no filesystem access.
- Terminates on cyclic graphs (iterative DFS with color-marking).
- Duplicate edges are deduplicated deterministically before processing.
- Dangling edges (referencing a dependency ID not in the snapshot) are
  counted and reported in limitations, never fabricated.
- Depth defaults to -1 when unknown; never invented.
- All unsupported ecosystems are retained in the output unchanged.
"""
import logging
from collections import defaultdict
from typing import Dict, Iterator, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from app.services.reporting.report_data import ReportData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class DependencyNode(BaseModel):
    """
    Snapshot-sourced representation of a single dependency within the
    relationship graph. All ID fields are exact snapshot values — never
    synthesised or inferred from package names.
    """
    dependency_id: str
    package_name: str
    ecosystem: str
    package_version: str
    dependency_type: str
    is_direct: bool
    parent_ids: List[str] = Field(default_factory=list)
    child_ids: List[str] = Field(default_factory=list)
    depth: int  # -1 when unknown (edges absent or node unreachable from root)
    relationship_type: Optional[str] = None  # from first incoming edge; None if root or no edges


class DependencyTreeResult(BaseModel):
    """
    Top-level result of the dependency tree analysis.

    edges_available: True only when the snapshot contains edge data (schema >= 1.1.0).
    When False, parent_ids/child_ids are empty and depth is -1 for all nodes.

    cycle_detected: Set to True conservatively. When True the graph is not
    acyclic; depth values for cyclic nodes may not reflect true tree depth.

    limitations: Explicit, factual list of data quality constraints for this
    particular result. Never a legal or policy claim.
    """
    scan_id: str
    project_id: str
    total_dependencies: int
    direct_count: int
    non_direct_count: int
    edges_available: bool
    cycle_detected: bool
    orphan_count: int
    nodes: List[DependencyNode] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers — pure functions, no side-effects
# ---------------------------------------------------------------------------

def _dedup_edges(edges) -> list:
    """
    Deduplicate snapshot edges by (parent_id, child_id, relationship_type, depth).
    Deterministic: first-seen wins (edges are pre-sorted in the snapshot).
    """
    seen: Set[Tuple] = set()
    result = []
    for e in edges:
        key = (e.parent_id, e.child_id, e.relationship_type, e.depth)
        if key not in seen:
            seen.add(key)
            result.append(e)
    return result


def _detect_cycle(
    dep_ids: Iterator[str],
    child_map: Dict[str, List[str]],
) -> bool:
    """
    Iterative DFS cycle detection using three-color marking.

    WHITE (0) = not yet visited
    GRAY  (1) = currently on the DFS stack
    BLACK (2) = fully processed

    Returns True as soon as a back-edge (to a GRAY node) is found.
    Never recurses — uses an explicit stack to avoid Python recursion limits.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    colors: Dict[str, int] = {dep_id: WHITE for dep_id in dep_ids}

    for start in list(colors.keys()):
        if colors[start] != WHITE:
            continue
        # Stack entries: (node_id, iterator-over-children)
        stack = [(start, iter(child_map.get(start, [])))]
        colors[start] = GRAY

        while stack:
            node, children_iter = stack[-1]
            try:
                child = next(children_iter)
                if child not in colors:
                    # Dangling reference (filtered out earlier, but be safe)
                    continue
                if colors[child] == GRAY:
                    return True   # Back-edge found → cycle
                if colors[child] == WHITE:
                    colors[child] = GRAY
                    stack.append((child, iter(child_map.get(child, []))))
            except StopIteration:
                colors[node] = BLACK
                stack.pop()

    return False


def _compute_bfs_depths(
    root_ids: List[str],
    child_map: Dict[str, List[str]],
    known_ids: Set[str],
) -> Dict[str, int]:
    """
    BFS from root nodes to assign minimum depth (root = 0).
    Only visits nodes in known_ids. Returns a partial dict — nodes
    unreachable from any root will be absent.
    """
    from collections import deque

    depths: Dict[str, int] = {}
    queue: deque = deque()

    for root in root_ids:
        if root not in depths:
            depths[root] = 0
            queue.append(root)

    while queue:
        node = queue.popleft()
        node_depth = depths[node]
        for child in child_map.get(node, []):
            if child in known_ids and child not in depths:
                depths[child] = node_depth + 1
                queue.append(child)

    return depths


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class DependencyTreeAnalyzer:
    """
    Offline dependency relationship analyzer.

    Consumes ReportData (read-only) and produces DependencyTreeResult.
    Works correctly whether or not edge data is present in the snapshot.

    Behavior guarantees:
    - read-only (no mutation of ReportData or any nested structure)
    - offline (no DB, no network, no filesystem)
    - terminates on cycles (iterative DFS)
    - deterministic: identical input → identical output ordering
    - graceful degradation when edges are absent
    """

    def analyze(self, report_data: ReportData) -> DependencyTreeResult:
        """
        Build the dependency tree result from snapshot data.

        Args:
            report_data: A completed scan's ReportData. Treated as read-only.

        Returns:
            A new DependencyTreeResult. Input is unchanged.
        """
        # ------------------------------------------------------------------ #
        # 1. Build dependency lookup (ID → dep)                               #
        # ------------------------------------------------------------------ #
        dep_map = {dep.id: dep for dep in report_data.dependencies}
        known_ids: Set[str] = set(dep_map.keys())
        limitations: List[str] = []

        # ------------------------------------------------------------------ #
        # 2. Determine edge availability                                       #
        # ------------------------------------------------------------------ #
        raw_edges = list(report_data.edges)  # shallow copy — no mutation

        # Determine edge availability from snapshot schema version, not edge count.
        #
        #   Schema 1.0.0 → "edges" key absent from snapshot payload.
        #                  edges_available = False (data was never serialized).
        #
        #   Schema 1.1.0, edges = [] → "edges" key present; scanner produced 0
        #                  relationships for this scan.
        #                  edges_available = True (capability confirmed; count = 0).
        #
        #   Schema 1.1.0, edges = [...] → relationship data available.
        #                  edges_available = True.
        _EDGE_CAPABLE_SCHEMAS: frozenset = frozenset({"1.1.0"})
        snapshot_schema = report_data.metadata.get("schema_version", "1.0.0")
        edges_available = snapshot_schema in _EDGE_CAPABLE_SCHEMAS

        if not edges_available:
            limitations.append(
                "Dependency edge data is not available in this snapshot "
                "(snapshot schema 1.0.0 predates edge serialization). "
                "Parent/child relationships and depth values cannot be computed."
            )
        elif not raw_edges:
            limitations.append(
                "Dependency edge data capability is present (snapshot schema 1.1.0) "
                "but 0 relationships were recorded for this scan. "
                "The scanner may not have populated relationship edges for this "
                "package manager or manifest type."
            )

        # ------------------------------------------------------------------ #
        # 3. Deduplicate edges                                                 #
        # ------------------------------------------------------------------ #
        dedup_edges = _dedup_edges(raw_edges)

        # ------------------------------------------------------------------ #
        # 4. Filter dangling edges                                             #
        # ------------------------------------------------------------------ #
        valid_edges = []
        dangling_count = 0
        for edge in dedup_edges:
            if edge.parent_id in known_ids and edge.child_id in known_ids:
                valid_edges.append(edge)
            else:
                dangling_count += 1

        if dangling_count > 0:
            limitations.append(
                f"{dangling_count} edge(s) reference dependency ID(s) not present "
                f"in the snapshot and were ignored."
            )

        # ------------------------------------------------------------------ #
        # 5. Build adjacency maps                                              #
        # ------------------------------------------------------------------ #
        # parent_map[child_id] = sorted list of unique parent_ids
        # child_map[parent_id]  = sorted list of unique child_ids
        # rel_type_map[child_id] = relationship_type from first incoming edge
        parent_map: Dict[str, Set[str]] = defaultdict(set)
        child_map: Dict[str, Set[str]] = defaultdict(set)
        edge_depth_map: Dict[str, int] = {}    # child_id → minimum depth from edges
        rel_type_map: Dict[str, str] = {}      # child_id → first incoming rel_type

        for edge in valid_edges:
            parent_map[edge.child_id].add(edge.parent_id)
            child_map[edge.parent_id].add(edge.child_id)

            # Track minimum edge-provided depth for each child node
            if edge.depth is not None and edge.depth >= 0:
                existing = edge_depth_map.get(edge.child_id)
                if existing is None or edge.depth < existing:
                    edge_depth_map[edge.child_id] = edge.depth

            # First-seen relationship type for each child node
            if edge.child_id not in rel_type_map:
                rel_type_map[edge.child_id] = edge.relationship_type

        # Freeze to sorted lists for deterministic output
        parent_map_sorted: Dict[str, List[str]] = {
            k: sorted(v) for k, v in parent_map.items()
        }
        child_map_sorted: Dict[str, List[str]] = {
            k: sorted(v) for k, v in child_map.items()
        }

        # ------------------------------------------------------------------ #
        # 6. Cycle detection                                                   #
        # ------------------------------------------------------------------ #
        cycle_detected = False
        if edges_available and valid_edges:
            cycle_detected = _detect_cycle(
                iter(known_ids),
                child_map_sorted,
            )
            if cycle_detected:
                limitations.append(
                    "Cycle detected in the dependency graph. "
                    "Depth values may be unreliable for nodes within the cyclic subgraph. "
                    "The analyzer never claims the dependency graph is acyclic."
                )

        # ------------------------------------------------------------------ #
        # 7. BFS depth assignment (from direct/root nodes)                    #
        # ------------------------------------------------------------------ #
        # Root nodes: deps that are direct (is_direct=True) or have no parents
        # in the edge map. We use BFS to compute minimum depth from roots.
        bfs_depths: Dict[str, int] = {}
        if edges_available and valid_edges and not cycle_detected:
            root_ids = [
                dep.id for dep in report_data.dependencies
                if dep.is_direct or dep.id not in parent_map_sorted
            ]
            bfs_depths = _compute_bfs_depths(root_ids, child_map_sorted, known_ids)

        # ------------------------------------------------------------------ #
        # 8. Build nodes (deterministic sort: ecosystem, package, version)    #
        # ------------------------------------------------------------------ #
        sorted_deps = sorted(
            report_data.dependencies,
            key=lambda d: (d.ecosystem.lower(), d.package_name.lower(), d.package_version),
        )

        nodes: List[DependencyNode] = []
        for dep in sorted_deps:
            parents = parent_map_sorted.get(dep.id, [])
            children = child_map_sorted.get(dep.id, [])

            # Depth resolution
            if not edges_available:
                depth = -1
            elif dep.is_direct and not parents:
                depth = 0  # Root node — direct dependency with no parent edges
            elif dep.id in bfs_depths:
                depth = bfs_depths[dep.id]
            elif dep.id in edge_depth_map:
                depth = edge_depth_map[dep.id]
            else:
                depth = -1  # Unreachable from roots or cycle prevented BFS

            rel_type = rel_type_map.get(dep.id) if edges_available else None

            nodes.append(
                DependencyNode(
                    dependency_id=dep.id,
                    package_name=dep.package_name,
                    ecosystem=dep.ecosystem,
                    package_version=dep.package_version,
                    dependency_type=dep.dependency_type,
                    is_direct=dep.is_direct,
                    parent_ids=parents,
                    child_ids=children,
                    depth=depth,
                    relationship_type=rel_type,
                )
            )

        # ------------------------------------------------------------------ #
        # 9. Summary counts                                                    #
        # ------------------------------------------------------------------ #
        direct_count = sum(1 for n in nodes if n.is_direct)
        non_direct_count = sum(1 for n in nodes if not n.is_direct)

        if edges_available:
            # Orphan: non-direct dep with no parent and no child edges
            orphan_count = sum(
                1 for n in nodes
                if not n.is_direct and not n.parent_ids and not n.child_ids
            )
        else:
            orphan_count = 0  # Cannot determine without edge data

        return DependencyTreeResult(
            scan_id=report_data.scan.id,
            project_id=report_data.metadata.get("project_id", "UNKNOWN"),
            total_dependencies=len(nodes),
            direct_count=direct_count,
            non_direct_count=non_direct_count,
            edges_available=edges_available,
            cycle_detected=cycle_detected,
            orphan_count=orphan_count,
            nodes=nodes,
            limitations=limitations,
        )
