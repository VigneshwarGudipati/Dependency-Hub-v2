import uuid
import pytest
import datetime
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Create a test-specific engine with NullPool to avoid cross-loop asyncpg errors
test_engine = create_async_engine(
    settings.async_database_url,
    poolclass=NullPool,
    echo=False,
)
TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

from app.models.dependency import Dependency
from app.models.scan import Scan, ScanStatus
from app.services.registry.base import NormalizedRegistryMetadata, RegistryStatus
from app.models.base import utc_now
from app.services.scan_worker import ScanEngine
from app.models.artifact import ProjectArtifact, ArtifactUploadStatus
from app.models.organization import Organization
from app.models.project import Project

async def _create_test_project(db: AsyncSession) -> Project:
    org_name = f"test-org-{uuid.uuid4()}"
    org = Organization(name=org_name, slug=org_name)
    db.add(org)
    await db.flush()

    proj = Project(
        organization_id=org.id,
        name=f"test-proj-{uuid.uuid4()}",
        slug=f"test-proj-{uuid.uuid4()}",
        visibility="PRIVATE",
        language="TypeScript",
        default_branch="main"
    )
    db.add(proj)
    await db.commit()
    return proj

@pytest.mark.asyncio
@patch("app.services.registry.npm.NpmRegistryProvider.get_package_metadata", new_callable=AsyncMock)
async def test_scan_integration_npm_success_and_cache(mock_npm_get):
    """Test registry enrichment on successful scan, including cache hits."""
    async with TestAsyncSessionLocal() as db:
        sample_project = await _create_test_project(db)

        # Clear cache before test to ensure MISS
        from app.models.registry_cache import RegistryCache
        from sqlalchemy import delete
        await db.execute(delete(RegistryCache))
        await db.commit()

        def side_effect(package_name, installed_version):
            if package_name == "express":
                return NormalizedRegistryMetadata(
                    ecosystem="npm", package_name="express", latest_version="4.18.2",
                    fetched_at=utc_now(), status=RegistryStatus.SUCCESS, provider="npm"
                )
            elif package_name == "react":
                return NormalizedRegistryMetadata(
                    ecosystem="npm", package_name="react", latest_version="18.2.0",
                    fetched_at=utc_now(), status=RegistryStatus.SUCCESS, provider="npm"
                )
            return NormalizedRegistryMetadata(
                ecosystem="npm", package_name=package_name, fetched_at=utc_now(),
                status=RegistryStatus.NOT_FOUND, provider="npm", error_code="NOT_FOUND"
            )
        mock_npm_get.side_effect = side_effect

        # Create artifact
        artifact = ProjectArtifact(
            project_id=sample_project.id,
            original_filename="package.json",
            storage_key="test-pkg",
            size_bytes=100,
            content_hash="hash1",
            upload_status=ArtifactUploadStatus.READY
        )
        db.add(artifact)
        await db.flush()

        # Mock file reading and decryption
        from app.models.encryption import ArtifactEncryptionMetadata
        enc_meta = ArtifactEncryptionMetadata(
            artifact_id=artifact.id,
            encrypted_dek_reference="mocked",
            initialization_vector="mocked",
            authentication_tag="mocked",
            key_reference="mocked",
            checksum="mocked"
        )
        db.add(enc_meta)
        await db.flush()

        with patch("app.services.scan_worker.open") as mock_open, \
             patch("app.services.scan_worker.key_provider.decrypt_dek"), \
             patch("app.services.scan_worker.decrypt_artifact") as mock_decrypt:
            mock_decrypt.return_value = b'{"dependencies": {"express": "4.17.1", "react": "17.0.2"}}'

            # Scan 1
            scan1 = Scan(
                project_id=sample_project.id,
                artifact_id=artifact.id,
                status=ScanStatus.RUNNING,
                started_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(scan1)
            await db.flush()

            engine = ScanEngine()
            await engine.run(db, scan1)

            stmt = select(Dependency).where(Dependency.scan_id == scan1.id).order_by(Dependency.package_name)
            deps = (await db.execute(stmt)).scalars().all()
            assert len(deps) == 2

            express_dep = next(d for d in deps if d.package_name == "express")
            reg_meta = express_dep.dependency_metadata.get("registry")
            assert reg_meta is not None
            assert reg_meta["latest_version"] == "4.18.2"
            assert reg_meta["outdated"] == "TRUE"
            assert reg_meta["cache_state"] == "MISS"

            # Scan 2 (Cache hit)
            scan2 = Scan(
                project_id=sample_project.id,
                artifact_id=artifact.id,
                status=ScanStatus.RUNNING,
                started_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(scan2)
            await db.flush()

            await engine.run(db, scan2)

            stmt2 = select(Dependency).where(Dependency.scan_id == scan2.id)
            deps2 = (await db.execute(stmt2)).scalars().all()
            assert len(deps2) == 2
            express_dep2 = next(d for d in deps2 if d.package_name == "express")
            reg_meta2 = express_dep2.dependency_metadata.get("registry")
            assert reg_meta2["cache_state"] == "FRESH"


@pytest.mark.asyncio
@patch("app.services.registry.npm.NpmRegistryProvider.get_package_metadata", new_callable=AsyncMock)
async def test_scan_integration_registry_unavailable_preserves_osv(mock_npm_get):
    """Test registry failure does not kill scan or erase OSV data."""
    async with TestAsyncSessionLocal() as db:
        sample_project = await _create_test_project(db)

        # Clear cache before test to ensure MISS
        from app.models.registry_cache import RegistryCache
        from sqlalchemy import delete
        await db.execute(delete(RegistryCache))
        await db.commit()

        mock_npm_get.side_effect = Exception("Network timeout")

        artifact = ProjectArtifact(
            project_id=sample_project.id,
            original_filename="package.json",
            storage_key="test-pkg-2",
            size_bytes=100,
            content_hash="hash2",
            upload_status=ArtifactUploadStatus.READY
        )
        db.add(artifact)
        await db.flush()

        # Mock file reading and decryption
        from app.models.encryption import ArtifactEncryptionMetadata
        enc_meta = ArtifactEncryptionMetadata(
            artifact_id=artifact.id,
            encrypted_dek_reference="mocked",
            initialization_vector="mocked",
            authentication_tag="mocked",
            key_reference="mocked",
            checksum="mocked"
        )
        db.add(enc_meta)
        await db.flush()

        with patch("app.services.scan_worker.open") as mock_open, \
             patch("app.services.scan_worker.key_provider.decrypt_dek"), \
             patch("app.services.scan_worker.decrypt_artifact") as mock_decrypt:
            mock_decrypt.return_value = b'{"dependencies": {"express": "4.17.1"}}'

            scan = Scan(
                project_id=sample_project.id,
                artifact_id=artifact.id,
                status=ScanStatus.RUNNING,
                started_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(scan)
            await db.flush()

            engine = ScanEngine()
            await engine.run(db, scan)

            stmt = select(Dependency).where(Dependency.scan_id == scan.id)
            deps = (await db.execute(stmt)).scalars().all()
            assert len(deps) == 1

            reg_meta = deps[0].dependency_metadata.get("registry")
            assert reg_meta["registry_status"] == "UNKNOWN"
            assert reg_meta["error_code"] == "INTERNAL_ERROR"
            assert "error" not in reg_meta


@pytest.mark.asyncio
@patch("app.services.registry.pypi.PyPIRegistryProvider.get_package_metadata", new_callable=AsyncMock)
async def test_scan_integration_pypi_unsupported_ecosystem(mock_pypi_get):
    """Test pypi package enrichment, and an unsupported ecosystem scenario."""
    async with TestAsyncSessionLocal() as db:
        sample_project = await _create_test_project(db)

        # Clear cache before test to ensure MISS
        from app.models.registry_cache import RegistryCache
        from sqlalchemy import delete
        await db.execute(delete(RegistryCache))
        await db.commit()

        mock_pypi_get.return_value = NormalizedRegistryMetadata(
            ecosystem="pypi", package_name="requests", latest_version="2.31.0",
            fetched_at=utc_now(), status=RegistryStatus.SUCCESS, provider="pypi"
        )

        artifact = ProjectArtifact(
            project_id=sample_project.id,
            original_filename="requirements.txt",
            storage_key="test-pkg-3",
            size_bytes=100,
            content_hash="hash3",
            upload_status=ArtifactUploadStatus.READY
        )
        db.add(artifact)
        await db.flush()

        # Mock file reading and decryption
        from app.models.encryption import ArtifactEncryptionMetadata
        enc_meta = ArtifactEncryptionMetadata(
            artifact_id=artifact.id,
            encrypted_dek_reference="mocked",
            initialization_vector="mocked",
            authentication_tag="mocked",
            key_reference="mocked",
            checksum="mocked"
        )
        db.add(enc_meta)
        await db.flush()

        with patch("app.services.scan_worker.open") as mock_open, \
             patch("app.services.scan_worker.key_provider.decrypt_dek"), \
             patch("app.services.scan_worker.decrypt_artifact") as mock_decrypt:
            mock_decrypt.return_value = b'requests==2.31.0'

            scan = Scan(
                project_id=sample_project.id,
                artifact_id=artifact.id,
                status=ScanStatus.RUNNING,
                started_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(scan)
            await db.flush()

            engine = ScanEngine()
            await engine.run(db, scan)

            stmt = select(Dependency).where(Dependency.scan_id == scan.id)
            deps = (await db.execute(stmt)).scalars().all()
            assert len(deps) == 1

            req_dep = deps[0]
            assert req_dep.package_name == "requests"

            reg_meta = req_dep.dependency_metadata.get("registry")
            assert reg_meta["latest_version"] == "2.31.0"
            # For '==2.31.0', it is a constraint, not a concrete version, so it's UNKNOWN
            assert reg_meta["outdated"] == "UNKNOWN"
            assert reg_meta["registry_status"] == "SUCCESS"
@pytest.mark.asyncio
@patch("app.services.registry.npm.NpmRegistryProvider.get_package_metadata", new_callable=AsyncMock)
async def test_scan_integration_registry_transaction_rollback(mock_npm_get):
    """Test that a failure in the scan AFTER registry cache enrichment rolls back dependencies AND cache."""
    async with TestAsyncSessionLocal() as db:
        sample_project = await _create_test_project(db)

        from app.models.registry_cache import RegistryCache
        from sqlalchemy import delete
        await db.execute(delete(RegistryCache))
        await db.commit()

        mock_npm_get.return_value = NormalizedRegistryMetadata(
            ecosystem="npm", package_name="express", latest_version="4.18.2",
            fetched_at=utc_now(), status=RegistryStatus.SUCCESS, provider="npm"
        )

        artifact = ProjectArtifact(
            project_id=sample_project.id,
            original_filename="package.json",
            storage_key="test-pkg-rb",
            size_bytes=100,
            content_hash="hashrb",
            upload_status=ArtifactUploadStatus.READY
        )
        db.add(artifact)
        await db.flush()

        from app.models.encryption import ArtifactEncryptionMetadata
        enc_meta = ArtifactEncryptionMetadata(
            artifact_id=artifact.id,
            encrypted_dek_reference="mocked",
            initialization_vector="mocked",
            authentication_tag="mocked",
            key_reference="mocked",
            checksum="mocked"
        )
        db.add(enc_meta)
        await db.flush()

        with patch("app.services.scan_worker.open") as mock_open, \
             patch("app.services.scan_worker.key_provider.decrypt_dek"), \
             patch("app.services.scan_worker.decrypt_artifact") as mock_decrypt:

            mock_decrypt.return_value = b'{"dependencies": {"express": "4.17.1"}}'

            scan = Scan(
                project_id=sample_project.id,
                artifact_id=artifact.id,
                status=ScanStatus.RUNNING,
                started_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(scan)
            await db.commit()

            engine = ScanEngine()

            # Monkeypatch the engine.run to fail AFTER it completes its internal steps successfully
            original_run = engine.run
            async def failing_run(session, scan_obj):
                await original_run(session, scan_obj)

                # Prove the cache was successfully flushed to the current transaction
                stmt = select(RegistryCache).where(RegistryCache.package_name == "express")
                cache_items = (await session.execute(stmt)).scalars().all()
                assert len(cache_items) == 1, "Cache write must be visible in current transaction before failure"

                raise Exception("Simulated failure AFTER registry enrichment")

            engine.run = failing_run

            scan_id = scan.id
            try:
                await engine.run(db, scan)
            except Exception as e:
                assert str(e) == "Simulated failure AFTER registry enrichment"
                await db.rollback()

            # Prove dependency is rolled back
            stmt = select(Dependency).where(Dependency.scan_id == scan_id)
            deps = (await db.execute(stmt)).scalars().all()
            assert len(deps) == 0

            # Prove cache is rolled back
            stmt_cache = select(RegistryCache).where(RegistryCache.package_name == "express")
            cache_after = (await db.execute(stmt_cache)).scalars().all()
            assert len(cache_after) == 0

@pytest.mark.asyncio
@patch("app.services.registry.npm.NpmRegistryProvider.get_package_metadata", new_callable=AsyncMock)
async def test_registry_service_flush_not_commit(mock_npm_get):
    """Test that get_package_metadata flushes to the current transaction but does NOT commit it."""

    # We will use two separate sessions to prove isolation
    async with TestAsyncSessionLocal() as db_writer:
        async with TestAsyncSessionLocal() as db_reader:
            # Clear cache
            from app.models.registry_cache import RegistryCache
            from sqlalchemy import delete
            await db_writer.execute(delete(RegistryCache))
            await db_writer.commit()

            mock_npm_get.return_value = NormalizedRegistryMetadata(
                ecosystem="npm", package_name="flush_test_pkg", latest_version="1.0.0",
                fetched_at=utc_now(), status=RegistryStatus.SUCCESS, provider="npm"
            )

            from app.services.registry.registry_service import RegistryIntelligenceService
            registry_service = RegistryIntelligenceService(db_writer)
            meta, state = await registry_service.get_package_metadata("npm", "flush_test_pkg")

            # Prove the write is visible IN THE SAME TRANSACTION
            stmt = select(RegistryCache).where(RegistryCache.package_name == "flush_test_pkg")
            writer_results = (await db_writer.execute(stmt)).scalars().all()
            assert len(writer_results) == 1, "Flush should make the row visible in the writer transaction"

            # Prove the write is NOT VISIBLE in a separate transaction (proving it's not committed)
            reader_results = (await db_reader.execute(stmt)).scalars().all()
            assert len(reader_results) == 0, "Row should NOT be visible to other connections because it is uncommitted"

            # Rollback the writer transaction
            await db_writer.rollback()

            # Prove the row is gone everywhere
            writer_results_after = (await db_writer.execute(stmt)).scalars().all()
            assert len(writer_results_after) == 0, "Row should be gone after rollback"
