import pytest
import uuid
import tempfile
import asyncio
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.repository_acquisition_service import RepositoryAcquisitionService, RepositoryAcquisitionError

@pytest.fixture
def service():
    return RepositoryAcquisitionService()

def test_validate_url_valid(service):
    service._validate_url("https://github.com/expressjs/express.git")

def test_validate_url_invalid_scheme(service):
    with pytest.raises(RepositoryAcquisitionError, match="Unsupported repository scheme"):
        service._validate_url("ssh://git@github.com/express.git")
    with pytest.raises(RepositoryAcquisitionError, match="Unsupported repository scheme"):
        service._validate_url("http://github.com/express.git")
    with pytest.raises(RepositoryAcquisitionError, match="Unsupported repository scheme"):
        service._validate_url("file:///etc/passwd")

def test_validate_url_local_network(service):
    with pytest.raises(RepositoryAcquisitionError, match="Local or private network targets"):
        service._validate_url("https://localhost/repo.git")
    with pytest.raises(RepositoryAcquisitionError, match="Local or private network targets"):
        service._validate_url("https://127.0.0.1/repo.git")
    with pytest.raises(RepositoryAcquisitionError, match="Local or private network targets"):
        service._validate_url("https://mycompany.local/repo.git")

@pytest.mark.asyncio
async def test_acquire_manifest_success(service):
    """Test that a repo with a single package.json is acquired correctly."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = b""

    def fake_subprocess_run(cmd, **kwargs):
        # cmd[-1] is the destination directory
        target_dir = Path(cmd[-1])
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "package.json").write_text('{"name": "test-repo"}')
        return mock_result

    with patch.object(subprocess, "run", side_effect=fake_subprocess_run):
        filename, content = await service.acquire_manifest("https://github.com/test/repo.git")
        assert filename == "package.json"
        assert content == b'{"name": "test-repo"}'

@pytest.mark.asyncio
async def test_acquire_manifest_no_manifest(service):
    """Test that a repo with no manifest raises RepositoryAcquisitionError."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = b""

    def fake_subprocess_run(cmd, **kwargs):
        target_dir = Path(cmd[-1])
        target_dir.mkdir(parents=True, exist_ok=True)
        # No manifest files created intentionally
        return mock_result

    with patch.object(subprocess, "run", side_effect=fake_subprocess_run):
        with pytest.raises(RepositoryAcquisitionError, match="No supported manifest found"):
            await service.acquire_manifest("https://github.com/test/repo.git")

@pytest.mark.asyncio
async def test_acquire_manifest_ambiguous(service):
    """Test that a repo with multiple manifests raises RepositoryAcquisitionError."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = b""

    def fake_subprocess_run(cmd, **kwargs):
        target_dir = Path(cmd[-1])
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "package.json").write_text('{"name": "test"}')
        (target_dir / "requirements.txt").write_text('flask')
        return mock_result

    with patch.object(subprocess, "run", side_effect=fake_subprocess_run):
        with pytest.raises(RepositoryAcquisitionError, match="Multiple supported manifests found; manual selection required"):
            await service.acquire_manifest("https://github.com/test/repo.git")

@pytest.mark.asyncio
async def test_acquire_manifest_clone_fail(service):
    """Test that clone failures with auth errors are reported correctly."""
    mock_result = MagicMock()
    mock_result.returncode = 128
    mock_result.stderr = b"Authentication failed\nfatal: Authentication failed"

    with patch.object(subprocess, "run", return_value=mock_result):
        with pytest.raises(RepositoryAcquisitionError, match="Private repository authentication is not supported."):
            await service.acquire_manifest("https://github.com/test/private.git")

@pytest.mark.asyncio
async def test_acquire_manifest_timeout(service):
    """Test that clone timeouts are reported correctly."""
    def timeout_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 60.0)

    with patch.object(subprocess, "run", side_effect=timeout_run):
        with pytest.raises(RepositoryAcquisitionError, match="Git clone timed out"):
            await service.acquire_manifest("https://github.com/test/slow.git")
