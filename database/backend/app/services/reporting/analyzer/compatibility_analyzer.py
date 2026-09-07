import logging
from typing import List, Optional

from app.services.reporting.report_data import (
    ReportDependencyData,
    DependencyUpgradeAnalysis,
    CodeImpactData,
    BreakingChangeData,
    FailureRiskData,
)
from app.services.reporting.analyzer.dependency_upgrade_analyzer import get_version_distance

logger = logging.getLogger(__name__)


class CompatibilityAnalyzer:
    """
    Analyzes dependency upgrade compatibility using a strict evidence hierarchy.
    Side-effect free: returns a new DependencyUpgradeAnalysis object with enriched fields.
    """

    def analyze(
        self,
        dependency: ReportDependencyData,
        upgrade_analysis: DependencyUpgradeAnalysis,
        code_impacts: List[CodeImpactData],
    ) -> DependencyUpgradeAnalysis:
        # Clone the existing analysis to avoid in-place mutation
        enriched = upgrade_analysis.model_copy(deep=True)

        current_version = dependency.package_version
        recommended_version = upgrade_analysis.recommended_version
        ecosystem = dependency.ecosystem.lower()

        # 1. Unsupported ecosystem -> UNKNOWN
        if ecosystem not in ["npm", "yarn", "pnpm", "pypi", "pip"]:
            enriched.compatibility_risk = "UNKNOWN"
            enriched.manual_review_required = True
            enriched.breaking_changes = []
            return enriched

        if not recommended_version or recommended_version == "UNKNOWN":
            # Missing upgrade data -> MANUAL REVIEW REQUIRED
            enriched.compatibility_risk = "UNKNOWN"
            enriched.manual_review_required = True
            return enriched

        distance = get_version_distance(current_version, recommended_version, ecosystem)

        # 2. Check for authoritative breaking change metadata
        # (This simulates a verified signal if metadata was somehow present)
        registry_meta = dependency.registry_metadata
        verified_evidence = registry_meta.get("breaking_change_evidence")

        if verified_evidence:
            enriched.compatibility_risk = "HIGH"
            enriched.manual_review_required = True
            enriched.breaking_changes = [
                BreakingChangeData(
                    category="VERIFIED",
                    description=str(verified_evidence),
                    impact="Verified breaking changes introduced in recommended version."
                )
            ]
            return enriched

        # 3. Heuristics: Major version transition + Code Impacts
        valid_impacts = [c for c in code_impacts if c.detected_pattern not in {"NO_USAGE_FOUND", "SOURCE_UNAVAILABLE", "UNSUPPORTED_ECOSYSTEM", "PACKAGE_IMPORT_MAPPING_UNKNOWN"}]
        has_source_usage = len(valid_impacts) > 0
        files_affected = len(set([c.file_path for c in valid_impacts]))

        if distance == "MAJOR":
            if has_source_usage:
                enriched.compatibility_risk = "HIGH"
                enriched.manual_review_required = True
            else:
                enriched.compatibility_risk = "MEDIUM"
                enriched.manual_review_required = True
            return enriched

        # 4. No major transition, no explicit evidence -> MANUAL REVIEW REQUIRED
        enriched.compatibility_risk = "LOW" if distance in ["PATCH", "MINOR"] else "UNKNOWN"
        enriched.manual_review_required = True

        return enriched
