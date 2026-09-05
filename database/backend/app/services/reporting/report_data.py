from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class BreakingChangeData(BaseModel):
    category: str
    description: str
    impact: str

class CodeImpactData(BaseModel):
    file_path: str
    line_number: Optional[int] = None
    detected_pattern: str
    risk: str
    recommendation: str

class FailureRiskData(BaseModel):
    scenario: str
    risk: str
    trigger: str
    affected_area: str
    prevention: str

class DependencyUpgradeAnalysis(BaseModel):
    minimum_fixed_version: Optional[str] = None
    recommended_version: Optional[str] = None
    latest_known_version: Optional[str] = None
    manual_review_required: bool = False
    upgrade_risk: Optional[str] = None
    security_benefit: Optional[str] = None
    compatibility_risk: Optional[str] = None
    breaking_changes: List[BreakingChangeData] = Field(default_factory=list)
    code_impacts: List[CodeImpactData] = Field(default_factory=list)
    failure_risks: List[FailureRiskData] = Field(default_factory=list)
    exact_upgrade_command: Optional[str] = None
    resolved_vulnerabilities: List[str] = Field(default_factory=list)

class ReportProjectData(BaseModel):
    id: str
    name: str

class ReportScanData(BaseModel):
    id: str
    scan_type: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    scanner_version: str

class ReportSeverityCounts(BaseModel):
    CRITICAL: int = 0
    HIGH: int = 0
    MEDIUM: int = 0
    LOW: int = 0

class ReportSummaryData(BaseModel):
    total_packages: int
    vulnerable_packages: int
    vulnerability_findings: int
    severity_counts: ReportSeverityCounts

    # We will derive these two explicitly during instantiation from the dependencies payload
    outdated_packages: int = 0
    unknown_packages: int = 0

class ReportDependencyData(BaseModel):
    id: str
    package_name: str
    ecosystem: str
    package_version: str
    version_constraint: Optional[str] = None
    dependency_type: str
    is_direct: bool
    registry_metadata: Dict[str, Any] = Field(default_factory=dict)
    upgrade_analysis: Optional[DependencyUpgradeAnalysis] = None

    @property
    def outdated(self) -> str:
        """Normalized outdated state: 'TRUE', 'FALSE', or 'UNKNOWN'."""
        val = self.registry_metadata.get("outdated", "UNKNOWN")
        if val is True:
            return "TRUE"
        if val is False:
            return "FALSE"
        return "UNKNOWN"

    @property
    def latest_version(self) -> str:
        return self.registry_metadata.get("latest_version", "UNKNOWN")

class ReportVulnerabilityData(BaseModel):
    dependency_id: str
    vulnerability_id: str
    title: str
    severity: str
    finding_metadata: Dict[str, Any] = Field(default_factory=dict)
    remediation_status: Optional[str] = None

    @property
    def patched_version(self) -> str:
        return self.finding_metadata.get("patched_version", "UNKNOWN")

    @property
    def affected_versions(self) -> str:
        return self.finding_metadata.get("affected_versions", "UNKNOWN")

class ReportSafeUpgradePlan(BaseModel):
    before_upgrade: List[str] = Field(default_factory=list)
    during_upgrade: List[str] = Field(default_factory=list)
    after_upgrade: List[str] = Field(default_factory=list)

class ReportData(BaseModel):
    """
    Strict, normalized representation of the historical ReportSnapshot.
    Exposes validated domain facts strictly conforming to the 1 package / 25 findings rule.
    """
    metadata: Dict[str, Any]
    project: ReportProjectData
    scan: ReportScanData
    summary: ReportSummaryData
    dependencies: List[ReportDependencyData]
    vulnerabilities: List[ReportVulnerabilityData]
    safe_upgrade_plan: Optional[ReportSafeUpgradePlan] = None

    @classmethod
    def from_snapshot(cls, snapshot_data: Dict[str, Any]) -> "ReportData":
        """
        Parses and validates the raw snapshot envelope.
        Extracts `canonical_payload` + `metadata` and injects derived count metrics safely.
        """
        if "metadata" not in snapshot_data or "canonical_payload" not in snapshot_data:
            raise ValueError("INVALID_SNAPSHOT: Missing envelope metadata or canonical_payload")

        metadata = snapshot_data["metadata"]
        payload = snapshot_data["canonical_payload"]

        # Enforce schema version compatibility here in the future if multiple schemas exist
        schema_version = metadata.get("schema_version")
        if schema_version != "1.0.0":
            raise ValueError(f"UNSUPPORTED_SCHEMA_VERSION: {schema_version}")

        # Derive exact outdated/unknown counts locally to avoid relying on implicit snapshot gaps
        outdated_packages = 0
        unknown_packages = 0

        for dep in payload.get("dependencies", []):
            reg = dep.get("registry_metadata", {})
            outdated = reg.get("outdated", "UNKNOWN")
            if outdated is True:
                outdated_packages += 1
            elif outdated == "UNKNOWN" or outdated is None:
                unknown_packages += 1

        payload_summary = payload.get("summary", {})
        payload_summary["outdated_packages"] = outdated_packages
        payload_summary["unknown_packages"] = unknown_packages

        return cls(
            metadata=metadata,
            project=payload.get("project", {}),
            scan=payload.get("scan", {}),
            summary=payload_summary,
            dependencies=payload.get("dependencies", []),
            vulnerabilities=payload.get("vulnerabilities", []),
            safe_upgrade_plan=payload.get("safe_upgrade_plan")
        )
