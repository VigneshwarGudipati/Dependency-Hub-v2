"""Database seeding utility for reference data, system roles, permissions, and ecosystems."""

from typing import Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Role, SystemRoleName
from app.models.permission import Permission, RolePermission
from app.models.ecosystem import PackageEcosystem
from app.models.license import License, LicenseCategory, LicenseRiskLevel

DEFAULT_PERMISSIONS: List[Dict[str, str]] = [
    {"code": "organization.read", "description": "View organization details", "category": "organization"},
    {"code": "organization.update", "description": "Update organization settings", "category": "organization"},
    {"code": "member.read", "description": "View organization members", "category": "member"},
    {"code": "member.manage", "description": "Invite, update, or remove organization members", "category": "member"},
    {"code": "project.create", "description": "Create new projects", "category": "project"},
    {"code": "project.read", "description": "View project details and settings", "category": "project"},
    {"code": "project.update", "description": "Modify project settings", "category": "project"},
    {"code": "project.delete", "description": "Delete projects", "category": "project"},
    {"code": "project.upload", "description": "Upload new project artifacts/snapshots", "category": "project"},
    {"code": "scan.create", "description": "Trigger and schedule scans", "category": "scan"},
    {"code": "scan.read", "description": "View scan results and metrics", "category": "scan"},
    {"code": "scan.delete", "description": "Delete scan executions", "category": "scan"},
    {"code": "dependency.read", "description": "View project dependency graphs", "category": "dependency"},
    {"code": "dependency.manage", "description": "Override or manage dependency metadata", "category": "dependency"},
    {"code": "finding.read", "description": "View vulnerability and compliance findings", "category": "finding"},
    {"code": "finding.update", "description": "Triage, acknowledge, or resolve findings", "category": "finding"},
    {"code": "audit.read", "description": "View organization audit event trail", "category": "audit"},
    {"code": "report.create", "description": "Request new report generation", "category": "report"},
    {"code": "report.read", "description": "View report status and metadata", "category": "report"},
    {"code": "report.download", "description": "Download generated report artifacts", "category": "report"},
    {"code": "report.retry", "description": "Retry failed report generation", "category": "report"},
    {"code": "report.delete", "description": "Delete reports", "category": "report"},
]

ROLE_PERMISSION_MATRIX: Dict[SystemRoleName, List[str]] = {
    SystemRoleName.OWNER: [p["code"] for p in DEFAULT_PERMISSIONS],
    SystemRoleName.ADMIN: [
        p["code"] for p in DEFAULT_PERMISSIONS if p["code"] not in ["organization.delete"]
    ],
    SystemRoleName.DEVELOPER: [
        "organization.read",
        "member.read",
        "project.create",
        "project.read",
        "project.update",
        "project.upload",
        "scan.create",
        "scan.read",
        "dependency.read",
        "finding.read",
        "report.create",
        "report.read",
        "report.download",
        "report.retry",
        "report.delete",
    ],
    SystemRoleName.SECURITY_ANALYST: [
        "organization.read",
        "member.read",
        "project.read",
        "scan.create",
        "scan.read",
        "dependency.read",
        "finding.read",
        "finding.update",
        "audit.read",
        "report.create",
        "report.read",
        "report.download",
        "report.retry",
    ],
    SystemRoleName.VIEWER: [
        "organization.read",
        "member.read",
        "project.read",
        "scan.read",
        "dependency.read",
        "finding.read",
        "report.read",
        "report.download",
    ],
}

DEFAULT_ECOSYSTEMS: List[Dict[str, str]] = [
    {"name": "npm", "description": "Node.js JavaScript & TypeScript package ecosystem", "default_package_manager": "npm"},
    {"name": "PyPI", "description": "Python Package Index ecosystem", "default_package_manager": "pip"},
    {"name": "Maven", "description": "Java and JVM build ecosystem", "default_package_manager": "mvn"},
    {"name": "Gradle", "description": "Gradle multi-language build ecosystem", "default_package_manager": "gradle"},
    {"name": "NuGet", "description": ".NET package ecosystem", "default_package_manager": "nuget"},
    {"name": "Cargo", "description": "Rust package registry (crates.io)", "default_package_manager": "cargo"},
    {"name": "Go", "description": "Go module ecosystem", "default_package_manager": "go"},
    {"name": "RubyGems", "description": "Ruby gems package ecosystem", "default_package_manager": "gem"},
    {"name": "Composer", "description": "PHP dependency management ecosystem", "default_package_manager": "composer"},
]

DEFAULT_LICENSES: List[Dict[str, Any]] = [
    {"name": "MIT License", "spdx_identifier": "MIT", "category": LicenseCategory.PERMISSIVE, "risk_level": LicenseRiskLevel.NONE},
    {"name": "Apache License 2.0", "spdx_identifier": "Apache-2.0", "category": LicenseCategory.PERMISSIVE, "risk_level": LicenseRiskLevel.NONE},
    {"name": "BSD 3-Clause 'New' or 'Revised' License", "spdx_identifier": "BSD-3-Clause", "category": LicenseCategory.PERMISSIVE, "risk_level": LicenseRiskLevel.NONE},
    {"name": "BSD 2-Clause 'Simplified' License", "spdx_identifier": "BSD-2-Clause", "category": LicenseCategory.PERMISSIVE, "risk_level": LicenseRiskLevel.NONE},
    {"name": "GNU General Public License v3.0", "spdx_identifier": "GPL-3.0-only", "category": LicenseCategory.COPYLEFT, "risk_level": LicenseRiskLevel.HIGH},
    {"name": "GNU Lesser General Public License v3.0", "spdx_identifier": "LGPL-3.0-only", "category": LicenseCategory.WEAK_COPYLEFT, "risk_level": LicenseRiskLevel.MEDIUM},
    {"name": "Mozilla Public License 2.0", "spdx_identifier": "MPL-2.0", "category": LicenseCategory.WEAK_COPYLEFT, "risk_level": LicenseRiskLevel.LOW},
    {"name": "ISC License", "spdx_identifier": "ISC", "category": LicenseCategory.PERMISSIVE, "risk_level": LicenseRiskLevel.NONE},
    {"name": "The Unlicense", "spdx_identifier": "Unlicense", "category": LicenseCategory.PERMISSIVE, "risk_level": LicenseRiskLevel.NONE},
]


async def seed_reference_data(session: AsyncSession) -> Dict[str, int]:
    """Idempotently seed default permissions, roles, role permissions, ecosystems, and licenses."""
    counts = {"permissions": 0, "roles": 0, "role_permissions": 0, "ecosystems": 0, "licenses": 0}

    # 1. Seed Permissions
    perm_lookup: Dict[str, Permission] = {}
    for p_data in DEFAULT_PERMISSIONS:
        stmt = select(Permission).where(Permission.code == p_data["code"])
        result = await session.execute(stmt)
        perm = result.scalar_one_or_none()
        if not perm:
            perm = Permission(
                code=p_data["code"],
                description=p_data["description"],
                category=p_data["category"],
            )
            session.add(perm)
            await session.flush()
            counts["permissions"] += 1
        perm_lookup[p_data["code"]] = perm

    # 2. Seed Roles
    role_lookup: Dict[SystemRoleName, Role] = {}
    for role_name in SystemRoleName:
        stmt = select(Role).where(Role.name == role_name.value)
        result = await session.execute(stmt)
        role = result.scalar_one_or_none()
        if not role:
            role = Role(
                name=role_name.value,
                description=f"System {role_name.value.title()} role",
                is_system=True,
            )
            session.add(role)
            await session.flush()
            counts["roles"] += 1
        role_lookup[role_name] = role

    # 3. Seed Role-Permissions mappings
    for role_enum, perm_codes in ROLE_PERMISSION_MATRIX.items():
        role = role_lookup[role_enum]
        for code in perm_codes:
            perm = perm_lookup.get(code)
            if not perm:
                continue
            stmt = select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == perm.id,
            )
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                rp = RolePermission(role_id=role.id, permission_id=perm.id)
                session.add(rp)
                counts["role_permissions"] += 1

    # 4. Seed Package Ecosystems
    for eco_data in DEFAULT_ECOSYSTEMS:
        stmt = select(PackageEcosystem).where(PackageEcosystem.name == eco_data["name"])
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            eco = PackageEcosystem(
                name=eco_data["name"],
                description=eco_data["description"],
                default_package_manager=eco_data["default_package_manager"],
            )
            session.add(eco)
            counts["ecosystems"] += 1

    # 5. Seed Licenses
    for lic_data in DEFAULT_LICENSES:
        stmt = select(License).where(License.spdx_identifier == lic_data["spdx_identifier"])
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            lic = License(
                name=lic_data["name"],
                spdx_identifier=lic_data["spdx_identifier"],
                category=lic_data["category"],
                risk_level=lic_data["risk_level"],
            )
            session.add(lic)
            counts["licenses"] += 1

    await session.commit()
    return counts
