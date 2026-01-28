from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "CSOKi Site Selection Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/csoki_sites"

    # Redis (for caching)
    REDIS_URL: str = "redis://localhost:6379"

    # API Keys (to be configured)
    MAPBOX_ACCESS_TOKEN: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    CENSUS_API_KEY: Optional[str] = None

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://dashboard.fivecodevelopment.com",
        "https://frontend-production-12b6.up.railway.app",
    ]

    # Geocoding
    GEOCODING_USER_AGENT: str = "csoki-site-selection/1.0"
    GEOCODING_RATE_LIMIT: float = 1.0  # requests per second

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
