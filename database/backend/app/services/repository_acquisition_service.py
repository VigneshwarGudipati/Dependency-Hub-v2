import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException

class RepositoryAcquisitionError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)

class RepositoryAcquisitionService:
    SUPPORTED_MANIFESTS = ["package.json", "requirements.txt"]

    def _validate_url(self, url: str) -> None:
        if not url:
            raise RepositoryAcquisitionError("Repository URL is required for repository scan mode.")

        try:
            parsed = urlparse(url)
        except Exception:
            raise RepositoryAcquisitionError("Invalid repository URL format.")

        if parsed.scheme != "https":
            raise RepositoryAcquisitionError(f"Unsupported repository scheme: {parsed.scheme}. Only HTTPS is supported.")

        hostname = parsed.hostname
        if not hostname:
            raise RepositoryAcquisitionError("Invalid repository URL: Missing hostname.")

        # Reject obvious local/private targets
        blocked_domains = ["localhost", "127.0.0.1", "::1"]
        if hostname.lower() in blocked_domains or hostname.lower().endswith(".local"):
            raise RepositoryAcquisitionError("Local or private network targets are not supported.")

    async def acquire_manifest(self, repository_url: str) -> Tuple[str, bytes]:
        """
        Clones the repository securely and extracts the supported manifest.
        Returns a tuple of (filename, file_content_bytes).
        """
        self._validate_url(repository_url)

        temp_dir = Path(tempfile.gettempdir()) / f"dep_hub_clone_{uuid.uuid4()}"

        try:
            # 1. Clone repository
            import subprocess

            def _run_git():
                return subprocess.run(
                    ["git", "clone", "--depth", "1", repository_url, str(temp_dir)],
                    capture_output=True,
                    env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                    timeout=60.0
                )

            try:
                process = await asyncio.to_thread(_run_git)
            except subprocess.TimeoutExpired:
                raise RepositoryAcquisitionError("Failed to acquire repository manifest: Git clone timed out.")

            if process.returncode != 0:
                stderr_dec = process.stderr.decode('utf-8', errors='replace')
                if "Authentication failed" in stderr_dec or "could not read Username" in stderr_dec:
                    raise RepositoryAcquisitionError("Private repository authentication is not supported.")
                raise RepositoryAcquisitionError(f"Failed to acquire repository manifest. Stderr: {stderr_dec}")

            # 2. Discover Manifest
            found_manifests = []
            for item in temp_dir.iterdir():
                if item.is_file() and item.name in self.SUPPORTED_MANIFESTS:
                    found_manifests.append(item)

            if not found_manifests:
                raise RepositoryAcquisitionError("No supported manifest found in repository.")

            if len(found_manifests) > 1:
                # Apply priority or fail if ambiguous
                # If we have package.json, prefer it? The prompt says "If ambiguity remains, fail clearly"
                raise RepositoryAcquisitionError("Multiple supported manifests found; manual selection required.")

            manifest_path = found_manifests[0]
            with open(manifest_path, "rb") as f:
                content = f.read()

            return manifest_path.name, content

        finally:
            # 3. Secure Cleanup
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

repository_acquisition_service = RepositoryAcquisitionService()
