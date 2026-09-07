import logging
from typing import Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from app.services.reporting.report_data import ReportData

logger = logging.getLogger(__name__)

_UNKNOWN_ID = "UNKNOWN"

# Caution: these are the ONLY permitted comparison_status values.
_VALID_STATUSES = frozenset({
    "VERIFIED REMEDIATED",
    "VERIFIED STILL PRESENT",
    "PARTIALLY REMEDIATED",
    "POTENTIAL CHANGE",
    "MANUAL REVIEW REQUIRED",
    "UNKNOWN",
    "NO FOLLOW-UP SCAN",
})


class VulnerabilityComparisonResult(BaseModel):
    """
    Comparison result for a single vulnerability finding, keyed by
    vulnerability_id and dependency identity (package_name::ecosystem).
    Read-only: represents an observation, not a mutation of either snapshot.
    """
    vulnerability_id: str
    dependency_key: str
    baseline_version: Optional[str] = None
    followup_version: Optional[str] = None
    comparison_status: str
    comparison_note: Optional[str] = None


class ScanComparisonResult(BaseModel):
    """
    Top-level scan comparison result. Contains a summary status and a list
    of per-finding VulnerabilityComparisonResult entries.
    Never reflects mutations to either input ReportData.
    """
    baseline_scan_id: Optional[str] = None
    followup_scan_id: Optional[str] = None
    project_id: str
    comparison_status: str
    findings: List[VulnerabilityComparisonResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions, no side effects)
# ---------------------------------------------------------------------------

def _build_dep_key_map(report_data: ReportData) -> Dict[str, str]:
    """
    Returns a map: dependency_id (str) → 'package_name::ecosystem'.
    Used to derive stable cross-scan dependency identity without relying on
    scan-scoped row UUIDs.
    """
    return {
        dep.id: f"{dep.package_name}::{dep.ecosystem}"
        for dep in report_data.dependencies
    }


def _build_version_map(report_data: ReportData) -> Dict[str, str]:
    """Returns a map: dependency_id → package_version."""
    return {dep.id: dep.package_version for dep in report_data.dependencies}


def _build_dep_key_to_version(
    dep_key_map: Dict[str, str],
    version_map: Dict[str, str],
) -> Dict[str, str]:
    """
    Returns a map: dependency_key → package_version.
    If multiple dependencies share the same logical key (unusual), the last
    one wins; callers treat the result as observational only.
    """
    result: Dict[str, str] = {}
    for dep_id, dep_key in dep_key_map.items():
        version = version_map.get(dep_id)
        if version is not None:
            result[dep_key] = version
    return result


def _compute_summary_status(findings: List[VulnerabilityComparisonResult]) -> str:
    """
    Derives the overall ScanComparisonResult.comparison_status from the
    individual finding statuses.

    Priority:
      - All NO FOLLOW-UP SCAN      → NO FOLLOW-UP SCAN
      - Mix of VERIFIED REMEDIATED
        and VERIFIED STILL PRESENT  → PARTIALLY REMEDIATED
      - Only VERIFIED REMEDIATED   → VERIFIED REMEDIATED
      - Only VERIFIED STILL PRESENT→ VERIFIED STILL PRESENT
      - Otherwise (UNKNOWN, MANUAL REVIEW REQUIRED, or empty) → MANUAL REVIEW REQUIRED
    """
    if not findings:
        return "UNKNOWN"

    status_set: Set[str] = {f.comparison_status for f in findings}

    if status_set == {"NO FOLLOW-UP SCAN"}:
        return "NO FOLLOW-UP SCAN"

    has_remediated = "VERIFIED REMEDIATED" in status_set
    has_still_present = "VERIFIED STILL PRESENT" in status_set

    if has_remediated and has_still_present:
        return "PARTIALLY REMEDIATED"
    if has_remediated:
        return "VERIFIED REMEDIATED"
    if has_still_present:
        return "VERIFIED STILL PRESENT"

    return "MANUAL REVIEW REQUIRED"


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class ScanComparisonAnalyzer:
    """
    Compares a baseline ReportData snapshot against an optional follow-up
    ReportData snapshot to produce remediation intelligence.

    Guarantees:
    - Neither input object is ever mutated.
    - Baseline findings are never injected into follow-up.vulnerabilities.
    - Remediation status is determined solely from observed finding presence
      or absence. No causal claims are made.
    - Only approved comparison_status values are emitted.
    """

    def analyze(
        self,
        baseline: Optional[ReportData],
        followup: Optional[ReportData],
    ) -> ScanComparisonResult:
        """
        Compare baseline and follow-up snapshots.

        Args:
            baseline: The earlier ReportData snapshot. Read-only.
            followup: The later ReportData snapshot, or None if unavailable.
                      Read-only when supplied.

        Returns:
            A new ScanComparisonResult. Neither input is modified.
        """
        if baseline is None:
            return self._handle_no_baseline(followup)

        if followup is None:
            return self._handle_no_followup(baseline)

        # Both snapshots present — enforce project identity
        baseline_project_id: str = baseline.metadata.get("project_id", "")
        followup_project_id: str = followup.metadata.get("project_id", "")

        if (
            not baseline_project_id
            or not followup_project_id
            or baseline_project_id != followup_project_id
        ):
            logger.warning(
                "scan_comparison_project_mismatch "
                f"baseline_project={baseline_project_id!r} "
                f"followup_project={followup_project_id!r}"
            )
            return ScanComparisonResult(
                baseline_scan_id=baseline.scan.id,
                followup_scan_id=followup.scan.id,
                project_id=baseline_project_id or "UNKNOWN",
                comparison_status="MANUAL REVIEW REQUIRED",
                findings=[],
            )

        findings = self._compare_findings(baseline, followup)
        summary = _compute_summary_status(findings)

        return ScanComparisonResult(
            baseline_scan_id=baseline.scan.id,
            followup_scan_id=followup.scan.id,
            project_id=baseline_project_id,
            comparison_status=summary,
            findings=findings,
        )

    # ------------------------------------------------------------------
    # Private: edge-case handlers
    # ------------------------------------------------------------------

    def _handle_no_baseline(
        self, followup: Optional[ReportData]
    ) -> ScanComparisonResult:
        """
        No baseline was supplied. Comparison cannot be performed.
        All follow-up findings (if any) receive MANUAL REVIEW REQUIRED.
        """
        if followup is None:
            return ScanComparisonResult(
                baseline_scan_id=None,
                followup_scan_id=None,
                project_id="UNKNOWN",
                comparison_status="MANUAL REVIEW REQUIRED",
                findings=[],
            )

        dep_key_map = _build_dep_key_map(followup)
        version_map = _build_version_map(followup)
        findings: List[VulnerabilityComparisonResult] = []

        for vuln in followup.vulnerabilities:
            dep_key = dep_key_map.get(vuln.dependency_id, "UNKNOWN::UNKNOWN")
            followup_version = version_map.get(vuln.dependency_id)
            findings.append(
                VulnerabilityComparisonResult(
                    vulnerability_id=vuln.vulnerability_id or _UNKNOWN_ID,
                    dependency_key=dep_key,
                    baseline_version=None,
                    followup_version=followup_version,
                    comparison_status="MANUAL REVIEW REQUIRED",
                    comparison_note=(
                        "No baseline snapshot was supplied. "
                        "Comparison cannot be performed."
                    ),
                )
            )

        return ScanComparisonResult(
            baseline_scan_id=None,
            followup_scan_id=followup.scan.id,
            project_id=followup.metadata.get("project_id", "UNKNOWN"),
            comparison_status="MANUAL REVIEW REQUIRED",
            findings=findings,
        )

    def _handle_no_followup(self, baseline: ReportData) -> ScanComparisonResult:
        """
        Baseline exists; no follow-up was supplied.
        All baseline findings receive NO FOLLOW-UP SCAN. No remediation is claimed.
        """
        dep_key_map = _build_dep_key_map(baseline)
        version_map = _build_version_map(baseline)
        findings: List[VulnerabilityComparisonResult] = []

        for vuln in baseline.vulnerabilities:
            dep_key = dep_key_map.get(vuln.dependency_id, "UNKNOWN::UNKNOWN")
            baseline_version = version_map.get(vuln.dependency_id)
            findings.append(
                VulnerabilityComparisonResult(
                    vulnerability_id=vuln.vulnerability_id or _UNKNOWN_ID,
                    dependency_key=dep_key,
                    baseline_version=baseline_version,
                    followup_version=None,
                    comparison_status="NO FOLLOW-UP SCAN",
                    comparison_note="No follow-up snapshot was supplied.",
                )
            )

        return ScanComparisonResult(
            baseline_scan_id=baseline.scan.id,
            followup_scan_id=None,
            project_id=baseline.metadata.get("project_id", "UNKNOWN"),
            comparison_status="NO FOLLOW-UP SCAN",
            findings=findings,
        )

    # ------------------------------------------------------------------
    # Private: main comparison logic
    # ------------------------------------------------------------------

    def _compare_findings(
        self,
        baseline: ReportData,
        followup: ReportData,
    ) -> List[VulnerabilityComparisonResult]:
        """
        Core comparison. Both inputs are read-only.

        Finding identity: exact equality of vulnerability_id.
        Dependency identity: (package_name, ecosystem) → 'package_name::ecosystem'.
        Cross-scan composite key: (vulnerability_id, dependency_key).

        The follow-up vulnerabilities list is never modified.
        """
        baseline_dep_map = _build_dep_key_map(baseline)
        followup_dep_map = _build_dep_key_map(followup)

        baseline_version_map = _build_version_map(baseline)
        followup_version_map = _build_version_map(followup)

        # dep_key → followup_version (for locating version of a dep that may
        # have lost a vulnerability — the dep still exists but the vuln is gone)
        followup_dep_key_to_version = _build_dep_key_to_version(
            followup_dep_map, followup_version_map
        )

        # Build follow-up finding index: (vulnerability_id, dependency_key) → followup_version
        # Key: composite (vid, dep_key) to correctly handle the same CVE affecting
        # multiple distinct packages independently.
        followup_index: Dict[Tuple[str, str], Optional[str]] = {}
        for vuln in followup.vulnerabilities:
            vid = vuln.vulnerability_id
            if not vid or vid == _UNKNOWN_ID:
                continue
            dep_key = followup_dep_map.get(vuln.dependency_id, "UNKNOWN::UNKNOWN")
            followup_version = followup_version_map.get(vuln.dependency_id)
            followup_index[(vid, dep_key)] = followup_version

        findings: List[VulnerabilityComparisonResult] = []

        # Track (vulnerability_id, dependency_key) pairs seen in baseline
        # to detect follow-up-only findings afterward.
        baseline_seen_pairs: Set[Tuple[str, str]] = set()

        # --- Pass 1: process every baseline finding ---
        for vuln in baseline.vulnerabilities:
            vid = vuln.vulnerability_id
            dep_key = baseline_dep_map.get(vuln.dependency_id, "UNKNOWN::UNKNOWN")
            baseline_version = baseline_version_map.get(vuln.dependency_id)

            # Missing or UNKNOWN identity: cannot compare
            if not vid or vid == _UNKNOWN_ID:
                findings.append(
                    VulnerabilityComparisonResult(
                        vulnerability_id=vid or _UNKNOWN_ID,
                        dependency_key=dep_key,
                        baseline_version=baseline_version,
                        followup_version=None,
                        comparison_status="MANUAL REVIEW REQUIRED",
                        comparison_note=(
                            "Finding identity is missing or UNKNOWN. "
                            "Comparison cannot be performed."
                        ),
                    )
                )
                continue

            pair = (vid, dep_key)
            baseline_seen_pairs.add(pair)

            if pair in followup_index:
                # Present in both snapshots
                followup_version = followup_index[pair]
                note = (
                    "The finding was present in the baseline and is present "
                    "in the complete follow-up scan."
                )
                if (
                    baseline_version
                    and followup_version
                    and baseline_version != followup_version
                ):
                    note += (
                        f" Dependency version changed from "
                        f"{baseline_version} to {followup_version}."
                    )
                findings.append(
                    VulnerabilityComparisonResult(
                        vulnerability_id=vid,
                        dependency_key=dep_key,
                        baseline_version=baseline_version,
                        followup_version=followup_version,
                        comparison_status="VERIFIED STILL PRESENT",
                        comparison_note=note,
                    )
                )
            else:
                # Present in baseline, absent from follow-up
                # Attempt to record the follow-up version of the same dependency
                # (the dependency may still exist in the follow-up even though
                # this specific finding no longer appears there).
                followup_version = followup_dep_key_to_version.get(dep_key)

                note = (
                    "The finding was present in the baseline and absent "
                    "from the complete follow-up scan."
                )
                if (
                    baseline_version
                    and followup_version
                    and baseline_version != followup_version
                ):
                    note += (
                        f" Dependency version changed from "
                        f"{baseline_version} to {followup_version}."
                    )
                findings.append(
                    VulnerabilityComparisonResult(
                        vulnerability_id=vid,
                        dependency_key=dep_key,
                        baseline_version=baseline_version,
                        followup_version=followup_version,
                        comparison_status="VERIFIED REMEDIATED",
                        comparison_note=note,
                    )
                )

        # --- Pass 2: follow-up-only findings (not seen in baseline) ---
        for vuln in followup.vulnerabilities:
            vid = vuln.vulnerability_id
            dep_key = followup_dep_map.get(vuln.dependency_id, "UNKNOWN::UNKNOWN")
            followup_version = followup_version_map.get(vuln.dependency_id)

            if not vid or vid == _UNKNOWN_ID:
                findings.append(
                    VulnerabilityComparisonResult(
                        vulnerability_id=vid or _UNKNOWN_ID,
                        dependency_key=dep_key,
                        baseline_version=None,
                        followup_version=followup_version,
                        comparison_status="MANUAL REVIEW REQUIRED",
                        comparison_note=(
                            "Finding identity is missing or UNKNOWN in "
                            "follow-up. Comparison cannot be performed."
                        ),
                    )
                )
                continue

            pair = (vid, dep_key)
            if pair not in baseline_seen_pairs:
                # Follow-up-only: no approved "NEW" status exists.
                # Conservative: MANUAL REVIEW REQUIRED.
                findings.append(
                    VulnerabilityComparisonResult(
                        vulnerability_id=vid,
                        dependency_key=dep_key,
                        baseline_version=None,
                        followup_version=followup_version,
                        comparison_status="MANUAL REVIEW REQUIRED",
                        comparison_note=(
                            "Finding present in follow-up but absent from "
                            "baseline. No baseline equivalent found."
                        ),
                    )
                )

        return findings
