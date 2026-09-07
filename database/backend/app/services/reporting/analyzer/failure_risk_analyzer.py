import logging
from typing import List

from app.services.reporting.report_data import (
    DependencyUpgradeAnalysis,
    CodeImpactData,
    FailureRiskData,
)

logger = logging.getLogger(__name__)


class FailureRiskAnalyzer:
    """
    Analyzes application failure risks based on compatibility signals and source usage evidence.
    Side-effect free: returns a new DependencyUpgradeAnalysis object with failure_risks populated.
    """

    def analyze(
        self,
        upgrade_analysis: DependencyUpgradeAnalysis,
        code_impacts: List[CodeImpactData],
    ) -> DependencyUpgradeAnalysis:
        enriched = upgrade_analysis.model_copy(deep=True)

        if not enriched.recommended_version or enriched.recommended_version == "UNKNOWN":
            enriched.failure_risks = [
                FailureRiskData(
                    scenario="Missing upgrade data",
                    risk="MANUAL REVIEW REQUIRED",
                    trigger="No recommended version available to evaluate.",
                    affected_area="Unknown",
                    prevention="Manual review required: authoritative migration guidance unavailable."
                )
            ]
            return enriched

        if enriched.compatibility_risk == "UNKNOWN":
            enriched.failure_risks = [
                FailureRiskData(
                    scenario="Unsupported ecosystem or missing data",
                    risk="UNKNOWN",
                    trigger="Ecosystem or upgrade path not supported for compatibility analysis.",
                    affected_area="Unknown",
                    prevention="Manual review required."
                )
            ]
            return enriched

        has_verified_breaking = any(bc.category == "VERIFIED" for bc in enriched.breaking_changes)

        valid_impacts = [c for c in code_impacts if c.detected_pattern not in {"NO_USAGE_FOUND", "SOURCE_UNAVAILABLE", "UNSUPPORTED_ECOSYSTEM", "PACKAGE_IMPORT_MAPPING_UNKNOWN"}]
        files_affected = len(set(c.file_path for c in valid_impacts))

        if has_verified_breaking:
            has_authoritative_impact = any(getattr(c, "risk", "") == "VERIFIED" for c in valid_impacts)

            if has_authoritative_impact:
                enriched.failure_risks = [
                    FailureRiskData(
                        scenario="Verified application failure risk from breaking change",
                        risk="VERIFIED",
                        trigger="Authoritative migration metadata and usage mapping explicitly confirms application impact.",
                        affected_area="Package Integration",
                        prevention="Validation required before deployment: Follow official migration guidance to update affected usages."
                    )
                ]
            elif files_affected > 0:
                affected_desc = "multiple files" if files_affected > 1 else "1 source file"
                enriched.failure_risks = [
                    FailureRiskData(
                        scenario="Potential application failure risk from verified breaking change",
                        risk="HIGH",
                        trigger=f"Verified breaking change with generic source usage in {affected_desc}",
                        affected_area="Affected source files identified by static analysis",
                        prevention="Validation required before deployment: Review affected files against breaking changes."
                    )
                ]
            else:
                enriched.failure_risks = [
                    FailureRiskData(
                        scenario="Potential application failure risk from verified breaking change",
                        risk="MEDIUM",
                        trigger="Verified breaking change without identified direct source usage",
                        affected_area="Application stability",
                        prevention="Validation required before deployment: Review transitive usages."
                    )
                ]
            return enriched

        # Compatibility risk HIGH or MEDIUM indicates a Major version transition in Phase E
        if enriched.compatibility_risk in ["HIGH", "MEDIUM"]:
            if files_affected > 0:
                affected_desc = "multiple files" if files_affected > 1 else "1 source file"
                enriched.failure_risks = [
                    FailureRiskData(
                        scenario="Potential application failure risk from dependency compatibility change",
                        risk="HIGH",
                        trigger=f"Major-version transition with direct source usage in {affected_desc}",
                        affected_area="Affected source files identified by static analysis",
                        prevention="Validation required before deployment: Run compatibility, integration, and pre-production validation."
                    )
                ]
            else:
                enriched.failure_risks = [
                    FailureRiskData(
                        scenario="Potential application failure risk from dependency compatibility change",
                        risk="MEDIUM",
                        trigger="Major-version transition without identified direct source usage",
                        affected_area="Application stability",
                        prevention="Validation required before deployment. Review transitive usages."
                    )
                ]
        else:
            if files_affected > 0:
                enriched.failure_risks = [
                    FailureRiskData(
                        scenario="Application behavior may be affected",
                        risk="LOW",
                        trigger="Minor or patch transition with direct source usage.",
                        affected_area="Package Integration",
                        prevention="Manual review required: standard pre-deployment validation."
                    )
                ]
            else:
                enriched.failure_risks = [
                    FailureRiskData(
                        scenario="No material failure signal identified",
                        risk="LOW",
                        trigger="No authoritative breaking change evidence or direct source usage found.",
                        affected_area="Unknown",
                        prevention="Standard validation required."
                    )
                ]

        return enriched
