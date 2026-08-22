import uuid
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import ProjectArtifact
from app.models.project import Project
from app.models.scan import Scan, ScanStatus
from app.schemas.scan import ScanCreate
from app.services.scan_worker import scan_worker


async def create_scan(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    scan_in: ScanCreate,
    background_tasks: BackgroundTasks
) -> Scan:
    """Create a new scan and schedule it to run in the background."""
    
    # 1. Authorize project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Authorize artifact exists and belongs to project
    result = await db.execute(
        select(ProjectArtifact)
        .where(ProjectArtifact.id == scan_in.artifact_id, ProjectArtifact.project_id == project_id)
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found in this project")
    
    # 3. Create Scan record in QUEUED state
    scan = Scan(
        project_id=project_id,
        artifact_id=scan_in.artifact_id,
        initiated_by=user_id,
        scan_type=scan_in.scan_type,
        status=ScanStatus.QUEUED,
        configuration=scan_in.configuration
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    
    # 4. Schedule the worker
    # We must not pass the `db` session into the background task, 
    # as the current request will close it. The worker manages its own session.
    background_tasks.add_task(scan_worker.execute_scan, scan.id)
    
    return scan


async def get_scan(
    db: AsyncSession,
    project_id: uuid.UUID,
    scan_id: uuid.UUID
) -> Scan:
    """Retrieve a scan by ID, ensuring it belongs to the project."""
    stmt = select(Scan).where(Scan.id == scan_id, Scan.project_id == project_id)
    result = await db.execute(stmt)
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan
