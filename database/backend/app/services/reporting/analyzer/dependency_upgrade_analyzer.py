import logging
import semver
from typing import List, Optional
from packaging.version import parse as parse_version, InvalidVersion

from app.services.reporting.report_data import (
    ReportDependencyData,
    ReportVulnerabilityData,
    DependencyUpgradeAnalysis,
)

logger = logging.getLogger(__name__)

def compare_semver(v1: str, v2: str) -> int:
    try:
        v1_parsed = semver.VersionInfo.parse(v1.lstrip('v='))
        v2_parsed = semver.VersionInfo.parse(v2.lstrip('v='))
        return v1_parsed.compare(v2_parsed)
    except ValueError as e:
        raise ValueError(f"Invalid semver: {e}")

def compare_pep440(v1: str, v2: str) -> int:
    try:
        pv1 = parse_version(v1)
        pv2 = parse_version(v2)
        if pv1 < pv2: return -1
        if pv1 > pv2: return 1
        return 0
    except InvalidVersion:
        raise ValueError(f"Invalid PEP440 version: {v1} or {v2}")

def compare_versions(v1: str, v2: str, ecosystem: str) -> int:
    ecosystem = ecosystem.lower()
    if ecosystem in ["npm", "yarn", "pnpm"]:
        return compare_semver(v1, v2)
    elif ecosystem in ["pypi", "pip"]:
        return compare_pep440(v1, v2)
    else:
        raise ValueError(f"Unsupported ecosystem for comparison: {ecosystem}")

def get_version_distance(current: str, target: str, ecosystem: str) -> str:
    ecosystem = ecosystem.lower()
    if ecosystem in ["npm", "yarn", "pnpm"]:
        try:
            c = semver.VersionInfo.parse(current.lstrip('v='))
            t = semver.VersionInfo.parse(target.lstrip('v='))
            if t.major > c.major: return "MAJOR"
            if t.minor > c.minor: return "MINOR"
            if t.patch > c.patch: return "PATCH"
            return "PATCH"
        except ValueError:
            return "UNKNOWN"
    elif ecosystem in ["pypi", "pip"]:
        try:
            c = parse_version(current)
            t = parse_version(target)
            if hasattr(c, 'release') and hasattr(t, 'release') and c.release and t.release:
                if t.release[0] > c.release[0]: return "MAJOR"
                if len(t.release) > 1 and len(c.release) > 1 and t.release[1] > c.release[1]: return "MINOR"
                if len(t.release) > 2 and len(c.release) > 2 and t.release[2] > c.release[2]: return "PATCH"
                return "PATCH"
        except (InvalidVersion, TypeError, IndexError):
            pass
    return "UNKNOWN"

class DependencyUpgradeAnalyzer:
    """
    Analyzes vulnerable dependencies to determine the optimal secure upgrade path.
    Strictly read-only and deterministic based on provided evidence.
    """

    def analyze(self, dependency: ReportDependencyData, vulnerabilities: List[ReportVulnerabilityData]) -> Optional[DependencyUpgradeAnalysis]:
        if not vulnerabilities:
            return None

        current_version = dependency.package_version
        latest_version = dependency.latest_version if dependency.latest_version != "UNKNOWN" else None
        ecosystem = dependency.ecosystem

        vuln_candidates = []
        for v in vulnerabilities:
            pv_str = v.patched_version
            if not pv_str or pv_str == "UNKNOWN":
                return self._build_manual_review(latest_version, vulnerabilities)

            candidates = [c.strip() for c in pv_str.split(',') if c.strip()]
            if not candidates:
                return self._build_manual_review(latest_version, vulnerabilities)
            vuln_candidates.append({"vuln_id": v.vulnerability_id, "candidates": candidates, "vuln_obj": v})

        all_candidates = set()
        for item in vuln_candidates:
            all_candidates.update(item["candidates"])

        resolving_candidates = []
        for candidate in all_candidates:
            resolves_all = True
            for item in vuln_candidates:
                resolved_this = False
                for fix in item["candidates"]:
                    try:
                        if compare_versions(candidate, fix, ecosystem) >= 0:
                            resolved_this = True
                            break
                    except ValueError:
                        pass
                if not resolved_this:
                    resolves_all = False
                    break

            if resolves_all:
                try:
                    if compare_versions(candidate, current_version, ecosystem) >= 0:
                        resolving_candidates.append(candidate)
                except ValueError:
                    pass

        # Identify minimum fixed version (lowest valid fix candidate overall >= current_version)
        minimum_fixed = None
        for candidate in all_candidates:
            try:
                if compare_versions(candidate, current_version, ecosystem) >= 0:
                    if minimum_fixed is None or compare_versions(candidate, minimum_fixed, ecosystem) < 0:
                        minimum_fixed = candidate
            except ValueError:
                pass

        if not resolving_candidates:
            return self._build_manual_review(latest_version, vulnerabilities, minimum_fixed=minimum_fixed)

        best_candidate = resolving_candidates[0]
        for candidate in resolving_candidates[1:]:
            try:
                if compare_versions(candidate, best_candidate, ecosystem) < 0:
                    best_candidate = candidate
            except ValueError:
                pass

        recommended = best_candidate

        # Verify which vulnerabilities this recommended version resolves
        resolved_vulns = []
        for item in vuln_candidates:
            for fix in item["candidates"]:
                try:
                    if compare_versions(recommended, fix, ecosystem) >= 0:
                        resolved_vulns.append(item["vuln_id"])
                        break
                except ValueError:
                    pass

        distance = get_version_distance(current_version, recommended, ecosystem)

        if distance == "MAJOR":
            upgrade_risk = "HIGH"
            compatibility_risk = "HIGH"
        elif distance == "MINOR":
            upgrade_risk = "MEDIUM"
            compatibility_risk = "MEDIUM"
        elif distance == "PATCH":
            upgrade_risk = "LOW"
            compatibility_risk = "LOW"
        else:
            upgrade_risk = "UNKNOWN"
            compatibility_risk = "UNKNOWN"

        security_benefit = self._calculate_security_benefit(vulnerabilities)

        return DependencyUpgradeAnalysis(
            minimum_fixed_version=minimum_fixed,
            recommended_version=recommended,
            latest_known_version=latest_version,
            manual_review_required=False,
            upgrade_risk=upgrade_risk,
            security_benefit=security_benefit,
            compatibility_risk=compatibility_risk,
            resolved_vulnerabilities=resolved_vulns,
            exact_upgrade_command=self._generate_upgrade_command(dependency, recommended)
        )

    def _build_manual_review(self, latest_version: Optional[str], vulnerabilities: List[ReportVulnerabilityData], minimum_fixed: Optional[str] = None) -> DependencyUpgradeAnalysis:
        return DependencyUpgradeAnalysis(
            minimum_fixed_version=minimum_fixed,
            latest_known_version=latest_version,
            manual_review_required=True,
            security_benefit=self._calculate_security_benefit(vulnerabilities)
        )

    def _calculate_security_benefit(self, vulnerabilities: List[ReportVulnerabilityData]) -> str:
        severities = [v.severity.upper() for v in vulnerabilities if v.severity]
        if "CRITICAL" in severities: return "CRITICAL"
        if "HIGH" in severities: return "HIGH"
        if "MEDIUM" in severities: return "MEDIUM"
        if "LOW" in severities: return "LOW"
        return "UNKNOWN"

    def _generate_upgrade_command(self, dependency: ReportDependencyData, recommended: Optional[str]) -> Optional[str]:
        if not recommended:
            return None
        ecosystem = dependency.ecosystem.lower()
        if ecosystem == "npm":
            return f"npm install {dependency.package_name}@{recommended}"
        elif ecosystem in ["pypi", "pip"]:
            return f"pip install {dependency.package_name}=={recommended}"
        elif ecosystem == "yarn":
            return f"yarn add {dependency.package_name}@{recommended}"
        return None
