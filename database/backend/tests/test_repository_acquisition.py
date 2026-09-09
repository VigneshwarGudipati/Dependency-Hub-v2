import pytest
import uuid
import tempfile
import asyncio
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
@patch("app.services.repository_acquisition_service.asyncio.create_subprocess_exec")
async def test_acquire_manifest_success(mock_create_subprocess, service):
    # Mock subprocess
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0
    mock_create_subprocess.return_value = mock_process

    with tempfile.TemporaryDirectory() as real_temp_dir:
        async def mock_communicate(*args, **kwargs):
            cloned_dir_path = mock_create_subprocess.call_args[0][5]
            Path(cloned_dir_path).mkdir(parents=True, exist_ok=True)
            with open(Path(cloned_dir_path) / "package.json", "w") as f:
                f.write('{"name": "test-repo"}')
            return (b"", b"")
                
            mock_process.communicate = mock_communicate
            
            filename, content = await service.acquire_manifest("https://github.com/test/repo.git")
            
            assert filename == "package.json"
            assert content == b'{"name": "test-repo"}'

@pytest.mark.asyncio
@patch("app.services.repository_acquisition_service.asyncio.create_subprocess_exec")
async def test_acquire_manifest_no_manifest(mock_create_subprocess, service):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0
    mock_create_subprocess.return_value = mock_process

    with tempfile.TemporaryDirectory() as real_temp_dir:
        async def mock_communicate(*args, **kwargs):
            cloned_dir_path = mock_create_subprocess.call_args[0][5]
            Path(cloned_dir_path).mkdir(parents=True, exist_ok=True)
            return (b"", b"")
                
            mock_process.communicate = mock_communicate
            
            with pytest.raises(RepositoryAcquisitionError, match="No supported manifest found"):
                await service.acquire_manifest("https://github.com/test/repo.git")

@pytest.mark.asyncio
@patch("app.services.repository_acquisition_service.asyncio.create_subprocess_exec")
async def test_acquire_manifest_ambiguous(mock_create_subprocess, service):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0
    mock_create_subprocess.return_value = mock_process

    with tempfile.TemporaryDirectory() as real_temp_dir:
        async def mock_communicate(*args, **kwargs):
            cloned_dir_path = mock_create_subprocess.call_args[0][5]
            Path(cloned_dir_path).mkdir(parents=True, exist_ok=True)
            with open(Path(cloned_dir_path) / "package.json", "w") as f:
                f.write('{"name": "test"}')
            with open(Path(cloned_dir_path) / "requirements.txt", "w") as f:
                f.write('flask')
            return (b"", b"")
            
        mock_process.communicate = mock_communicate
        
        with pytest.raises(RepositoryAcquisitionError, match="Multiple supported manifests found; manual selection required"):
            await service.acquire_manifest("https://github.com/test/repo.git")

@pytest.mark.asyncio
@patch("app.services.repository_acquisition_service.asyncio.create_subprocess_exec")
async def test_acquire_manifest_clone_fail(mock_create_subprocess, service):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"Authentication failed")
    mock_process.returncode = 128
    mock_create_subprocess.return_value = mock_process
    
    with pytest.raises(RepositoryAcquisitionError, match="Private repository authentication is not supported."):
        await service.acquire_manifest("https://github.com/test/private.git")

@pytest.mark.asyncio
@patch("app.services.repository_acquisition_service.asyncio.create_subprocess_exec")
async def test_acquire_manifest_timeout(mock_create_subprocess, service):
    mock_process = AsyncMock()
    
    async def mock_communicate(*args, **kwargs):
        raise asyncio.TimeoutError()
        
    mock_process.communicate = mock_communicate
    mock_create_subprocess.return_value = mock_process
    
    with pytest.raises(RepositoryAcquisitionError, match="Git clone timed out."):
        await service.acquire_manifest("https://github.com/test/slow.git")
