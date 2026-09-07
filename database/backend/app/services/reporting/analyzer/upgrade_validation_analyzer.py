"""
Phase L: UpgradeValidationAnalyzer

Produces structured, evidence-bounded information for:
1. Pre-Upgrade Checklist
2. Exact Upgrade Command
3. Rollback Plan
4. Post-Upgrade Validation Matrix

Does not imply upgrades were actually performed.
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from app.services.reporting.report_data import ReportData

class ValidationItem(BaseModel):
    category: str
    expected_result: str
    status: str = "NOT VERIFIED"
    evidence_source: str
    manual_action_required: bool = True

class RollbackPlan(BaseModel):
    restored_version: str
    procedural_steps: List[str]
    verification_steps: List[str]
    limitations: List[str]

class UpgradeValidationResult(BaseModel):
    dependency_id: str
    package_name: str
    current_version: str
    target_version: str
    exact_upgrade_command: str
    pre_upgrade_checklist: List[str]
    rollback_plan: RollbackPlan
    validations: List[ValidationItem]
    requires_manual_review: bool

class UpgradeValidationAnalyzer:
    """
    Offline analyzer that consumes ReportData to generate structured validation matrices
    and procedural rollback checklists.
    """

    def analyze(self, report_data: ReportData) -> List[UpgradeValidationResult]:
        results: List[UpgradeValidationResult] = []

        # We need vulnerability data to map remediation statuses to specific dependencies
        dep_remediation_statuses = {}
        for v in report_data.vulnerabilities:
            st = v.remediation_status or "UNKNOWN"
            # If multiple vulns exist for a dep, track the "worst" or just collect them.
            # For simplicity, we just keep the highest priority one or if any are VERIFIED STILL PRESENT
            current = dep_remediation_statuses.get(v.dependency_id, "UNKNOWN")
            if current != "VERIFIED STILL PRESENT":
                if st == "VERIFIED STILL PRESENT":
                    dep_remediation_statuses[v.dependency_id] = st
                elif current != "PARTIALLY REMEDIATED" and st == "PARTIALLY REMEDIATED":
                    dep_remediation_statuses[v.dependency_id] = st
                elif current not in ("VERIFIED REMEDIATED", "PARTIALLY REMEDIATED", "VERIFIED STILL PRESENT") and st == "VERIFIED REMEDIATED":
                    dep_remediation_statuses[v.dependency_id] = st
                elif current == "UNKNOWN":
                    dep_remediation_statuses[v.dependency_id] = st

        for dep in report_data.dependencies:
            ua = dep.upgrade_analysis
            if not ua:
                continue

            current_version = dep.package_version
            target_version = ua.recommended_version or "UNKNOWN"
            exact_command = ua.exact_upgrade_command or "UNKNOWN"
            requires_manual = ua.manual_review_required or exact_command == "UNKNOWN"

            # 1. Pre-Upgrade Checklist
            checklist = [
                f"Confirm current package version is {current_version}",
                f"Confirm recommended target version is {target_version}",
                "Review vulnerability evidence",
                "Review compatibility risk",
                "Review source-code impact",
                "Review application failure risk",
                "Back up/commit current state (PROCEDURAL GUIDANCE)",
                "Verify lockfile/manifest state (PROCEDURAL GUIDANCE)",
                "Run existing tests before upgrade (PROCEDURAL GUIDANCE)",
                "Record current scan/inventory (PROCEDURAL GUIDANCE)"
            ]

            # 2. Rollback Plan
            rollback = RollbackPlan(
                restored_version=current_version,
                procedural_steps=[
                    f"Revert package manifest to exact version {current_version}",
                    "Revert lockfile to pre-upgrade Git state",
                    "Clean package manager cache if necessary",
                    "Re-install dependencies from restored lockfile"
                ],
                verification_steps=[
                    f"Verify {dep.package_name} resolves exactly to {current_version}",
                    "Run existing application test suite"
                ],
                limitations=[
                    "Rollback assumes source control is available.",
                    "No infrastructure-specific or deployment rollback commands are provided."
                ]
            )

            # 3. Post-Upgrade Validation Matrix
            sec_status = dep_remediation_statuses.get(dep.id, "NO FOLLOW-UP SCAN")
            if sec_status == "UNKNOWN":
                sec_status = "NO FOLLOW-UP SCAN"

            validations = [
                ValidationItem(
                    category="Dependency installation",
                    expected_result="Package installs without errors",
                    status="NOT VERIFIED",
                    evidence_source="PROCEDURAL GUIDANCE",
                    manual_action_required=True
                ),
                ValidationItem(
                    category="Lockfile consistency",
                    expected_result="Lockfile updates successfully",
                    status="NOT VERIFIED",
                    evidence_source="PROCEDURAL GUIDANCE",
                    manual_action_required=True
                ),
                ValidationItem(
                    category="Application startup",
                    expected_result="Application boots without crash",
                    status="NOT VERIFIED",
                    evidence_source="PROCEDURAL GUIDANCE",
                    manual_action_required=True
                ),
                ValidationItem(
                    category="Unit tests",
                    expected_result="All unit tests pass",
                    status="NOT VERIFIED",
                    evidence_source="PROCEDURAL GUIDANCE",
                    manual_action_required=True
                ),
                ValidationItem(
                    category="Integration tests",
                    expected_result="All integration tests pass",
                    status="NOT VERIFIED",
                    evidence_source="PROCEDURAL GUIDANCE",
                    manual_action_required=True
                ),
                ValidationItem(
                    category="Build",
                    expected_result="Project compiles/builds successfully",
                    status="NOT VERIFIED",
                    evidence_source="PROCEDURAL GUIDANCE",
                    manual_action_required=True
                ),
                ValidationItem(
                    category="Lint/type checks",
                    expected_result="No new static analysis errors",
                    status="NOT VERIFIED",
                    evidence_source="PROCEDURAL GUIDANCE",
                    manual_action_required=True
                ),
                ValidationItem(
                    category="Smoke tests",
                    expected_result="Critical pathways function",
                    status="NOT VERIFIED",
                    evidence_source="PROCEDURAL GUIDANCE",
                    manual_action_required=True
                ),
                ValidationItem(
                    category="Security rescan",
                    expected_result="Vulnerabilities resolved",
                    status=sec_status,
                    evidence_source="SNAPSHOT SCAN COMPARISON" if sec_status != "NO FOLLOW-UP SCAN" else "PROCEDURAL GUIDANCE",
                    manual_action_required=sec_status == "NO FOLLOW-UP SCAN"
                ),
                ValidationItem(
                    category="Application-specific verification",
                    expected_result="Custom logic behaves correctly",
                    status="NOT VERIFIED",
                    evidence_source="PROCEDURAL GUIDANCE",
                    manual_action_required=True
                )
            ]

            results.append(
                UpgradeValidationResult(
                    dependency_id=dep.id,
                    package_name=dep.package_name,
                    current_version=current_version,
                    target_version=target_version,
                    exact_upgrade_command=exact_command,
                    pre_upgrade_checklist=checklist,
                    rollback_plan=rollback,
                    validations=validations,
                    requires_manual_review=requires_manual
                )
            )

        # Sort results deterministically by dependency_id
        results.sort(key=lambda x: x.dependency_id)
        return results
