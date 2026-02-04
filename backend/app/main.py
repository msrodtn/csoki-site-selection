from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.api import api_router
from app.models.store import Store
from app.models.team_property import TeamProperty  # Ensure table is created
from app.models.scraped_listing import ScrapedListing  # Ensure table is created


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to ensure redirects use HTTPS when behind a proxy."""
    async def dispatch(self, request: Request, call_next):
        # Check if we're behind a proxy using HTTPS
        forwarded_proto = request.headers.get("x-forwarded-proto", "http")
        if forwarded_proto == "https":
            # Update the scope to use https
            request.scope["scheme"] = "https"
        return await call_next(request)

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Create database tables (in production, use Alembic migrations)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")

    # Auto-seed database if empty
    db = SessionLocal()
    try:
        store_count = db.query(Store).count()
        if store_count == 0:
            logger.info("Database empty, seeding competitor data...")
            from app.services.data_import import import_all_competitors

            # Path to competitor data CSV files
            data_dir = Path(__file__).parent.parent / "data" / "competitors"

            if data_dir.exists():
                stats = import_all_competitors(db, data_dir, geocode=False)
                total_imported = sum(s.get('imported', 0) for s in stats.values())
                total_geocoded = sum(s.get('geocoded', 0) for s in stats.values())
                logger.info(f"Seeded {total_imported} stores ({total_geocoded} with coordinates)")
            else:
                logger.warning(f"Data directory not found: {data_dir}")
        else:
            logger.info(f"Database already contains {store_count} stores")
    except Exception as e:
        logger.error(f"Error during database seeding: {e}")
    finally:
        db.close()

    yield

    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered site selection platform for Cellular Sales",
    lifespan=lifespan,
)

# Add HTTPS redirect middleware (must be added before CORS)
app.add_middleware(HTTPSRedirectMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "healthy"
    }


@app.get("/health")
def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",  # TODO: Actually check connection
        "version": settings.APP_VERSION
    }
