"""Application settings and environment configuration."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Dependency Hub Application and Database Settings."""

    # Project metadata
    PROJECT_NAME: str = "Dependency Hub"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", alias="ENV")

    # PostgreSQL Connection Parameters
    POSTGRES_DB: str = "dependencyhub"
    POSTGRES_USER: str = "dependencyhub"
    POSTGRES_PASSWORD: str = "dependencyhub_dev_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Database URL
    DATABASE_URL: Optional[str] = None

    # Security / CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080", "http://localhost:8081"]

    # JWT Configuration
    JWT_SECRET: str = "CHANGE_ME_IN_PRODUCTION_USE_32_BYTES_MIN"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Artifact Configuration
    MAX_ARTIFACT_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB default
    ENCRYPTION_MASTER_KEY: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # 32 bytes hex for testing
    STORAGE_DIR: str = "storage"

    # Connection Pool Settings
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def async_database_url(self) -> str:
        """Construct or return the asyncpg database connection string."""
        if self.DATABASE_URL:
            # Ensure it uses postgresql+asyncpg://
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        """Construct or return a synchronous connection string (for Alembic or CLI)."""
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
                return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
