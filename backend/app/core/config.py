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

    # API Keys (active integrations)
    MAPBOX_ACCESS_TOKEN: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_PLACES_API_KEY: Optional[str] = None
    ARCGIS_API_KEY: Optional[str] = None
    REPORTALL_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    ATTOM_API_KEY: Optional[str] = None
    CREXI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    STREETLIGHT_API_KEY: Optional[str] = None
    CENSUS_API_KEY: Optional[str] = None
    FIRECRAWL_API_KEY: Optional[str] = None
    FIRECRAWL_MONTHLY_BUDGET: int = 400  # free tier = 500, leave 100 buffer
    MISSION_CONTROL_API_KEY: Optional[str] = None  # For Mission Control integration

    # Listing Scraper Credentials (for authenticated browser automation)
    CREXI_USERNAME: Optional[str] = None  # Also accepts CREXI_EMAIL
    CREXI_EMAIL: Optional[str] = None
    CREXI_PASSWORD: Optional[str] = None
    LOOPNET_USERNAME: Optional[str] = None
    LOOPNET_PASSWORD: Optional[str] = None

    # Geocoding
    GEOCODING_USER_AGENT: str = "csoki-site-selection/1.0"
    GEOCODING_RATE_LIMIT: float = 1.0

    @property
    def crexi_username(self) -> Optional[str]:
        """Get Crexi username from either CREXI_USERNAME or CREXI_EMAIL."""
        return self.CREXI_USERNAME or self.CREXI_EMAIL

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://dashboard.fivecodevelopment.com",
        "https://frontend-production-12b6.up.railway.app",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
