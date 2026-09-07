import logging
from typing import List, Optional

from app.services.reporting.report_data import (
    ReportDependencyData,
    ReportSafeUpgradePlan,
)

logger = logging.getLogger(__name__)


class SafeUpgradePlanAnalyzer:
    """
    Analyzes dependency upgrade analysis data to construct a conservative,
    actionable safe upgrade plan. Does not mutate input objects.
    """

    def analyze(self, dependencies: List[ReportDependencyData]) -> Optional[ReportSafeUpgradePlan]:
        if not dependencies:
            return None

        before = []
        during = []
        after = []

        has_plan = False

        for dep in dependencies:
            ua = dep.upgrade_analysis
            if not ua:
                continue

            has_plan = True

            # Extract failure risk level from Phase F
            failure_risk_str = "UNKNOWN"
            if ua.failure_risks:
                # Typically the primary failure risk is the first one
                failure_risk_str = ua.failure_risks[0].risk

            if ua.manual_review_required or not ua.recommended_version or ua.recommended_version == "UNKNOWN":
                before.append(
                    f"[{dep.package_name}] MANUAL REVIEW REQUIRED: Reliable upgrade path unavailable. "
                    f"Security benefit: {ua.security_benefit or 'UNKNOWN'}. "
                    "Review compatibility and source affected files manually."
                )
                during.append(
                    f"[{dep.package_name}] Manual review required: exact package-manager upgrade command unavailable. "
                    "Review dependency and lockfile changes."
                )
                after.append(
                    f"[{dep.package_name}] Perform rigorous application validation if manual upgrade is executed. "
                    "Maintain a known-good rollback path."
                )
                continue

            # Assess risk for caution text
            is_high_caution = False
            if ua.compatibility_risk in ["HIGH", "MEDIUM"] and failure_risk_str in ["HIGH", "VERIFIED"]:
                is_high_caution = True

            caution_text = (
                "High-caution upgrade. Review affected source usage and compatibility findings before deployment. "
                "Complete application validation before release."
            ) if is_high_caution else (
                "Review compatibility findings, affected source files, and expected dependency/lockfile changes."
            )

            # 1. BEFORE UPGRADE
            before.append(
                f"[{dep.package_name}] {dep.package_version} -> {ua.recommended_version} | "
                f"Security benefit: {ua.security_benefit or 'UNKNOWN'} | "
                f"Compatibility risk: {ua.compatibility_risk or 'UNKNOWN'} | "
                f"Application failure risk: {failure_risk_str}"
            )
            before.append(
                f"[{dep.package_name}] Pre-upgrade checks: Record current dependency version, "
                f"confirm a recoverable rollback point, and confirm existing validation coverage where known. {caution_text}"
            )

            # 2. DURING UPGRADE
            if ua.exact_upgrade_command:
                during.append(f"[{dep.package_name}] Run exactly: {ua.exact_upgrade_command}")
            else:
                during.append(
                    f"[{dep.package_name}] Manual review required: exact package-manager upgrade command unavailable. "
                    "Review dependency and lockfile changes."
                )

            # 3. AFTER UPGRADE (Validation & Rollback)
            after.append(
                f"[{dep.package_name}] Post-upgrade validation: Run existing unit tests. Run existing integration tests. "
                "Validate application startup. Exercise affected dependency functionality. Perform a security rescan and compare results where possible."
            )
            after.append(
                f"[{dep.package_name}] Rollback guidance: Restore the previously known-good dependency version and "
                "dependency/lockfile state if validation fails. Redeploy the previously known-good build using the project's existing deployment process."
            )

        if not has_plan:
            return None

        return ReportSafeUpgradePlan(
            before_upgrade=before,
            during_upgrade=during,
            after_upgrade=after
        )
