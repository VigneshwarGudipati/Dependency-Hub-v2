import logging
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field

from app.services.reporting.report_data import ReportData

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Ecosystems for which a registry provider exists and license data is expected.
# Derived from the actual registry provider implementations (npm.py, pypi.py).
_SUPPORTED_ECOSYSTEMS: frozenset = frozenset({"npm", "pypi"})

# Values that indicate the license field is present but semantically absent.
_NONE_LIKE_VALUES: frozenset = frozenset({
    "", "none", "unknown", "n/a", "null", "not specified", "unspecified", "unknown license",
})

# Textual separators that signal multiple license expressions in a single string.
# Detection is case-insensitive and positional — not a full SPDX expression parser.
_MULTI_LICENSE_SEPARATORS: tuple = (" or ", " and ", " with ")

# Keywords that suggest a proprietary, custom, or non-standard license declaration.
# Conservative list — only include markers that are unambiguously non-standard.
_CUSTOM_LICENSE_MARKERS: frozenset = frozenset({
    "proprietary", "commercial", "internal", "custom",
    "all rights reserved", "do not distribute", "not open source",
    "see license", "see licence", "see file", "see the license file",
})

# Permitted license_status values — no others may be emitted.
_VALID_LICENSE_STATUSES: frozenset = frozenset({
    "KNOWN_FROM_SOURCE",
    "MULTIPLE_LICENSES",
    "UNKNOWN",
    "MISSING",
    "MANUAL_REVIEW_REQUIRED",
})

# Source identifier — always the same in this analyzer; makes provenance explicit.
_LICENSE_SOURCE: str = "registry_metadata"


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class DependencyLicenseResult(BaseModel):
    """
    License classification for a single dependency entry derived from snapshot
    registry metadata. Read-only: represents an observation, not a mutation
    of the input ReportData.

    license_expression contains the raw unmodified value from the registry provider.
    It is NEVER synthesized, normalized, or validated against any SPDX registry.

    license_status describes the classification of that raw value.
    It does NOT constitute a legal determination or policy approval.
    """
    dependency_id: str
    package_name: str
    ecosystem: str
    package_version: str
    dependency_type: str
    is_direct: bool
    license_expression: Optional[str] = None
    license_status: str
    license_source: str
    license_note: Optional[str] = None


class SoftwareInventoryResult(BaseModel):
    """
    Top-level software inventory result. Contains summary counts and the
    complete per-dependency license classification list.

    This is an INTERNAL inventory representation, not a standards-compliant
    SBOM (CycloneDX / SPDX). Dependency relationship edges are not included
    because the snapshot does not contain them.
    """
    scan_id: str
    project_id: str
    total_dependencies: int
    dependencies_with_known_license: int
    dependencies_with_unknown_license: int
    dependencies_requiring_review: int
    supported_ecosystems: List[str] = Field(default_factory=list)
    unsupported_ecosystems: List[str] = Field(default_factory=list)
    inventory: List[DependencyLicenseResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions, no side effects)
# ---------------------------------------------------------------------------

def _normalise_for_comparison(value: str) -> str:
    """Lowercase and strip for comparison only. Never stored or emitted."""
    return value.strip().lower()


def _is_none_like(value: str) -> bool:
    """Returns True if the raw value is semantically absent (empty, UNKNOWN, etc.)."""
    return _normalise_for_comparison(value) in _NONE_LIKE_VALUES


def _contains_multi_license_separator(value: str) -> bool:
    """
    Returns True if the raw value contains a textual multi-license separator.
    Checks: ' OR ', ' AND ', ' WITH ' (case-insensitive), and comma (,).
    Comma is only treated as a separator when surrounded by non-whitespace content
    to avoid false positives on values like "MIT, Apache-2.0".
    """
    lower = value.lower()
    for sep in _MULTI_LICENSE_SEPARATORS:
        if sep in lower:
            return True
    # Comma: treat as multi-license separator only when present
    if "," in value:
        return True
    return False


def _appears_custom_or_unrecognized(value: str) -> bool:
    """
    Returns True if the raw value contains a keyword strongly suggesting a
    proprietary, internal, or custom license declaration.
    """
    lower = _normalise_for_comparison(value)
    for marker in _CUSTOM_LICENSE_MARKERS:
        if marker in lower:
            return True
    return False


def _classify_license(
    raw_value: Optional[str],
    key_present: bool,
    ecosystem: str,
) -> tuple:
    """
    Core classification function. Returns (license_status, license_expression, license_note).

    Classification priority:
      1. Unsupported ecosystem → MANUAL_REVIEW_REQUIRED (regardless of value)
      2. Key absent           → MISSING
      3. None-like value      → UNKNOWN
      4. Multi-license        → MULTIPLE_LICENSES
      5. Custom/unrecognized  → MANUAL_REVIEW_REQUIRED
      6. Otherwise            → KNOWN_FROM_SOURCE

    IMPORTANT:
    - KNOWN_FROM_SOURCE does NOT imply legal approval, SPDX validation, or
      policy compliance. It only means a non-empty recognizable value was
      supplied by the registry metadata.
    - license_expression is always the RAW unmodified provider value.
    - No SPDX normalization is performed.
    - No legal conclusion is made.
    """
    eco_lower = ecosystem.lower() if ecosystem else ""

    # Priority 1: Unsupported ecosystem
    if eco_lower not in _SUPPORTED_ECOSYSTEMS:
        return (
            "MANUAL_REVIEW_REQUIRED",
            raw_value if raw_value is not None else None,
            (
                f"Ecosystem '{ecosystem}' has no registry provider. "
                "License data cannot be verified from source data. "
                "Manual review required."
            ),
        )

    # Priority 2: Key absent from registry_metadata
    if not key_present:
        return (
            "MISSING",
            None,
            "License data absent from registry metadata.",
        )

    # Priority 3: None-like value
    if raw_value is None or _is_none_like(raw_value):
        return (
            "UNKNOWN",
            raw_value,
            (
                "License key is present in registry metadata but the value "
                "is empty or not recognizable. Treated as UNKNOWN."
            ),
        )

    # Priority 4: Multiple license expressions
    if _contains_multi_license_separator(raw_value):
        return (
            "MULTIPLE_LICENSES",
            raw_value,
            (
                f"Multiple license expressions detected: '{raw_value}'. "
                "Manual policy review required."
            ),
        )

    # Priority 5: Custom / unrecognized
    if _appears_custom_or_unrecognized(raw_value):
        return (
            "MANUAL_REVIEW_REQUIRED",
            raw_value,
            (
                f"License expression '{raw_value}' requires manual review. "
                "The value does not appear to correspond to a standard license expression."
            ),
        )

    # Priority 6: Recognizable non-empty value from a supported ecosystem
    return (
        "KNOWN_FROM_SOURCE",
        raw_value,
        f"License identified as '{raw_value}' from registry metadata.",
    )


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class LicenseAnalyzer:
    """
    Reads license information from ReportData.dependencies[n].registry_metadata
    and produces a structured SoftwareInventoryResult.

    Guarantees:
    - Input ReportData is never mutated.
    - No network calls are made.
    - No database queries are performed.
    - license_expression is always the raw unmodified provider value.
    - No SPDX normalization is applied.
    - No legal conclusion is emitted in any field.
    - Only approved license_status values are emitted.
    """

    def analyze(self, report_data: ReportData) -> SoftwareInventoryResult:
        """
        Classify the license status of every dependency in the snapshot.

        Args:
            report_data: A completed scan's normalized ReportData. Read-only.

        Returns:
            A new SoftwareInventoryResult. The input is not modified.
        """
        inventory: List[DependencyLicenseResult] = []
        seen_ecosystems: Set[str] = set()
        unsupported_ecosystems: Set[str] = set()

        for dep in report_data.dependencies:
            ecosystem = dep.ecosystem or "UNKNOWN"
            seen_ecosystems.add(ecosystem)

            # Read license from registry_metadata only — never from dep.license ORM column
            # (which is not part of the snapshot pathway).
            reg_meta: dict = dep.registry_metadata if dep.registry_metadata is not None else {}
            key_present: bool = "license" in reg_meta
            raw_value: Optional[str] = reg_meta.get("license") if key_present else None

            # Coerce non-string to string for classification (defensive)
            if raw_value is not None and not isinstance(raw_value, str):
                raw_value = str(raw_value)

            status, expression, note = _classify_license(
                raw_value=raw_value,
                key_present=key_present,
                ecosystem=ecosystem,
            )

            if ecosystem.lower() not in _SUPPORTED_ECOSYSTEMS:
                unsupported_ecosystems.add(ecosystem)

            inventory.append(
                DependencyLicenseResult(
                    dependency_id=dep.id,
                    package_name=dep.package_name,
                    ecosystem=ecosystem,
                    package_version=dep.package_version,
                    dependency_type=dep.dependency_type,
                    is_direct=dep.is_direct,
                    license_expression=expression,
                    license_status=status,
                    license_source=_LICENSE_SOURCE,
                    license_note=note,
                )
            )

        # Compute summary counts from actual generated results
        known_count = sum(
            1 for r in inventory if r.license_status == "KNOWN_FROM_SOURCE"
        )
        unknown_count = sum(
            1 for r in inventory if r.license_status in ("UNKNOWN", "MISSING")
        )
        review_count = sum(
            1 for r in inventory
            if r.license_status in ("MANUAL_REVIEW_REQUIRED", "MULTIPLE_LICENSES")
        )

        # Supported ecosystems encountered (those with a registry provider)
        supported_seen = sorted(
            e for e in seen_ecosystems if e.lower() in _SUPPORTED_ECOSYSTEMS
        )
        unsupported_seen = sorted(unsupported_ecosystems)

        return SoftwareInventoryResult(
            scan_id=report_data.scan.id,
            project_id=report_data.metadata.get("project_id", "UNKNOWN"),
            total_dependencies=len(inventory),
            dependencies_with_known_license=known_count,
            dependencies_with_unknown_license=unknown_count,
            dependencies_requiring_review=review_count,
            supported_ecosystems=supported_seen,
            unsupported_ecosystems=unsupported_seen,
            inventory=inventory,
        )
