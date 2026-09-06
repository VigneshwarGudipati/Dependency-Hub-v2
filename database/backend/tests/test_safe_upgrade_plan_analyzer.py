import pytest
from app.services.reporting.report_data import (
    ReportDependencyData,
    DependencyUpgradeAnalysis,
    FailureRiskData,
)
from app.services.reporting.analyzer.safe_upgrade_plan_analyzer import SafeUpgradePlanAnalyzer


@pytest.fixture
def analyzer():
    return SafeUpgradePlanAnalyzer()


def test_valid_recommended_upgrade_with_all_preservations(analyzer):
    # Tests 1, 2, 5, 6, 7, 8, 9, 10, 11, 14, 15, 16
    ua = DependencyUpgradeAnalysis(
        recommended_version="2.0.0",
        security_benefit="HIGH",
        compatibility_risk="LOW",
        exact_upgrade_command="npm install axios@2.0.0",
        failure_risks=[FailureRiskData(scenario="test", risk="LOW", trigger="x", affected_area="x", prevention="x")]
    )
    dep = ReportDependencyData(
        id="dep-1",
        package_name="axios",
        package_version="1.2.3",
        ecosystem="npm",
        dependency_type="dependencies",
        is_direct=True,
        upgrade_analysis=ua
    )

    res = analyzer.analyze([dep])
    assert res is not None

    before = " ".join(res.before_upgrade)
    during = " ".join(res.during_upgrade)
    after = " ".join(res.after_upgrade)

    # 1. Valid upgrade
    assert "1.2.3 -> 2.0.0" in before

    # 2. Phase C command reused
    assert "npm install axios@2.0.0" in during

    # 5. Security benefit preserved
    assert "Security benefit: HIGH" in before

    # 6. Compatibility risk preserved
    assert "Compatibility risk: LOW" in before

    # 7. Failure risk preserved
    assert "Application failure risk: LOW" in before

    # 8. Before-upgrade checklist
    assert "Pre-upgrade checks: Record current dependency version" in before

    # 9. During-upgrade instructions
    assert "Run exactly: npm install axios@2.0.0" in during

    # 10. Post-upgrade validation instructions
    assert "Post-upgrade validation: Run existing unit tests" in after

    # 11. Rollback guidance
    assert "Restore the previously known-good dependency version" in after

    # 14. No fabricated test results
    assert "Tests passed" not in after

    # 15. No fabricated rollback infrastructure commands
    assert "kubectl" not in after.lower()
    assert "docker" not in after.lower()

    # 16. No false safe upgrade guarantee
    assert "Upgrade is safe" not in before
    assert "Upgrade is safe" not in during
    assert "Upgrade is safe" not in after


def test_unavailable_recommended_version_and_manual_review(analyzer):
    # Tests 3, 12
    ua = DependencyUpgradeAnalysis(
        recommended_version=None,
        security_benefit="HIGH",
        manual_review_required=True
    )
    dep = ReportDependencyData(
        id="dep-1",
        package_name="axios",
        package_version="1.2.3",
        ecosystem="npm",
        dependency_type="dependencies",
        is_direct=True,
        upgrade_analysis=ua
    )

    res = analyzer.analyze([dep])
    before = " ".join(res.before_upgrade)

    assert "MANUAL REVIEW REQUIRED: Reliable upgrade path unavailable" in before
    assert "Security benefit: HIGH" in before


def test_unavailable_exact_command(analyzer):
    # Tests 4
    ua = DependencyUpgradeAnalysis(
        recommended_version="2.0.0",
        security_benefit="LOW",
        compatibility_risk="LOW",
        exact_upgrade_command=None
    )
    dep = ReportDependencyData(
        id="dep-1",
        package_name="axios",
        package_version="1.2.3",
        ecosystem="npm",
        dependency_type="dependencies",
        is_direct=True,
        upgrade_analysis=ua
    )

    res = analyzer.analyze([dep])
    during = " ".join(res.during_upgrade)
    assert "Manual review required: exact package-manager upgrade command unavailable" in during


def test_unknown_state_preservation(analyzer):
    # Tests 13
    ua = DependencyUpgradeAnalysis(
        recommended_version="2.0.0",
        security_benefit="UNKNOWN",
        compatibility_risk="UNKNOWN",
        exact_upgrade_command="npm install axios@2.0.0",
        failure_risks=[FailureRiskData(scenario="test", risk="UNKNOWN", trigger="x", affected_area="x", prevention="x")]
    )
    dep = ReportDependencyData(
        id="dep-1",
        package_name="axios",
        package_version="1.2.3",
        ecosystem="npm",
        dependency_type="dependencies",
        is_direct=True,
        upgrade_analysis=ua
    )

    res = analyzer.analyze([dep])
    before = " ".join(res.before_upgrade)
    assert "Security benefit: UNKNOWN" in before
    assert "Compatibility risk: UNKNOWN" in before
    assert "Application failure risk: UNKNOWN" in before


def test_high_caution_upgrade_logic(analyzer):
    # Ensures that POTENTIAL/HIGH compatibility + HIGH/VERIFIED failure triggers high caution
    ua = DependencyUpgradeAnalysis(
        recommended_version="2.0.0",
        security_benefit="HIGH",
        compatibility_risk="HIGH",
        exact_upgrade_command="npm install axios@2.0.0",
        failure_risks=[FailureRiskData(scenario="test", risk="VERIFIED", trigger="x", affected_area="x", prevention="x")]
    )
    dep = ReportDependencyData(
        id="dep-1",
        package_name="axios",
        package_version="1.2.3",
        ecosystem="npm",
        dependency_type="dependencies",
        is_direct=True,
        upgrade_analysis=ua
    )

    res = analyzer.analyze([dep])
    before = " ".join(res.before_upgrade)

    assert "High-caution upgrade. Review affected source usage and compatibility findings before deployment. Complete application validation before release." in before


def test_original_input_not_mutated(analyzer):
    ua = DependencyUpgradeAnalysis(
        recommended_version="2.0.0",
        exact_upgrade_command="npm install x@2"
    )
    dep = ReportDependencyData(
        id="dep-1",
        package_name="x",
        package_version="1",
        ecosystem="npm",
        dependency_type="dependencies",
        is_direct=True,
        upgrade_analysis=ua
    )

    _ = analyzer.analyze([dep])

    # Assert nothing changed
    assert dep.upgrade_analysis.recommended_version == "2.0.0"
    assert dep.upgrade_analysis.exact_upgrade_command == "npm install x@2"
