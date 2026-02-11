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

    # Auto-migrate: add transaction_type column if missing
    from sqlalchemy import text, inspect
    with engine.connect() as conn:
        inspector = inspect(engine)
        cols = [c["name"] for c in inspector.get_columns("scraped_listings")]
        if "transaction_type" not in cols:
            conn.execute(text(
                "ALTER TABLE scraped_listings ADD COLUMN transaction_type VARCHAR(20)"
            ))
            conn.commit()
            logger.info("Added transaction_type column to scraped_listings")

    # Auto-seed database and sync new stores from CSVs
    db = SessionLocal()
    try:
        from app.services.data_import import import_all_competitors

        store_count = db.query(Store).count()
        data_dir = Path(__file__).parent.parent / "data" / "competitors"

        if data_dir.exists():
            # Always run import with skip_existing=True to pick up new stores
            logger.info(f"Database has {store_count} stores, syncing from CSVs...")
            stats = import_all_competitors(db, data_dir, geocode=False)
            total_imported = sum(s.get('imported', 0) for s in stats.values())
            total_geocoded = sum(s.get('geocoded', 0) for s in stats.values())
            if total_imported > 0:
                logger.info(f"Imported {total_imported} new stores ({total_geocoded} with coordinates)")
            else:
                logger.info(f"All stores up to date ({store_count} in database)")
        else:
            logger.warning(f"Data directory not found: {data_dir}")
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

# Configure CORS - ensure all required origins are always included
# This prevents Railway env vars from accidentally overriding required origins
_required_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://dashboard.fivecodevelopment.com",
    "https://frontend-production-12b6.up.railway.app",
]
cors_origins = list(set(settings.CORS_ORIGINS + _required_origins))
logger.info(f"CORS origins configured: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
