from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from app.core.config import settings
from app.core.database import Base, get_engine, get_session_local, check_database_connection
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
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager with graceful error handling."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Quick startup - test database connection but don't block on failure
    try:
        if check_database_connection():
            logger.info("Database connection verified")

            # Create tables if needed
            engine = get_engine()
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created/verified")

            # Check store count (quick operation)
            SessionLocal = get_session_local()
            db = SessionLocal()
            try:
                store_count = db.query(Store).count()
                if store_count == 0:
                    logger.info("Database empty - stores will need to be imported")
                else:
                    logger.info(f"Database contains {store_count} stores")
            finally:
                db.close()
        else:
            logger.warning("Database connection failed - some features will be unavailable")
    except Exception as e:
        logger.error(f"Startup error (continuing anyway): {e}")

    logger.info("Application startup complete")
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
    """Root endpoint - quick health check."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
def health_check():
    """
    Detailed health check with actual database verification.
    Returns 200 if healthy, 503 if database is unreachable.
    """
    db_connected = check_database_connection()

    if db_connected:
        return {
            "status": "healthy",
            "database": "connected",
            "version": settings.APP_VERSION
        }
    else:
        return Response(
            content='{"status": "unhealthy", "database": "disconnected", "version": "' + settings.APP_VERSION + '"}',
            status_code=503,
            media_type="application/json"
        )
