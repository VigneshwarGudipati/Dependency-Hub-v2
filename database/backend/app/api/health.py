from fastapi import APIRouter, Depends
from app.schemas.health import HealthResponse, DatabaseHealthResponse, ReadinessResponse
from app.core.database import check_database_health

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
async def get_health():
    """Verify application liveness."""
    return {"status": "ok"}

@router.get("/health/database", response_model=DatabaseHealthResponse)
async def get_database_health():
    """Verify database connectivity."""
    db_status = await check_database_health()
    return db_status

@router.get("/ready", response_model=ReadinessResponse)
async def get_readiness():
    """Verify application readiness to serve traffic."""
    # Assuming if the app reaches here, it is serving traffic.
    # We also check DB status for complete readiness.
    db_status = await check_database_health()
    status = "ok" if db_status.get("status") == "healthy" else "unavailable"
    return {"status": status, "database": db_status.get("status")}

# A test endpoint to force an exception ONLY for testing purposes.
# We will inject this only during tests, so we won't define it here,
# or we'll rely on the test_app.py to add the route temporarily.
