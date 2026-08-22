from fastapi import APIRouter
from app.schemas.health import ApiVersionResponse

api_router = APIRouter()

@api_router.get("", response_model=ApiVersionResponse)
async def get_version():
    """Return API version information."""
    return {"name": "Dependency Hub API", "version": "v1"}
