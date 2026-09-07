from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import close_database_engine
from app.core.exceptions import validation_exception_handler, http_exception_handler, global_exception_handler
from app.core.middleware import RequestIDMiddleware, StructuredLoggingMiddleware
from app.api.health import router as health_router
from app.api.v1.router import api_router as v1_router
from app.api.auth import router as auth_router

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan_context(app: FastAPI):
    yield
    await close_database_engine()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Dependency Hub Backend API Foundation",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan_context
)

# Exception Handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# Middleware
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1.projects import router as projects_router
from app.api.v1.members import router as members_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.dependencies import router as dependencies_router
from app.api.v1.vulnerabilities import router as vulnerabilities_router
from app.api.v1.reports import router as reports_router

# Routers
app.include_router(health_router, tags=["System"])
app.include_router(v1_router, prefix="/api/v1", tags=["System"])
app.include_router(auth_router, prefix="/api/v1", tags=["Authentication"])
app.include_router(projects_router, prefix="/api/v1")
app.include_router(members_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(dependencies_router, prefix="/api/v1")
app.include_router(vulnerabilities_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
