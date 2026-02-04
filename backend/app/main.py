from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.api import api_router


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
    """Application lifecycle manager - fast startup for Railway health checks."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("Application startup complete")
    yield
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
    Health check endpoint - instant response for Railway.
    No database check here - that would slow down the response.
    """
    return {"status": "healthy", "version": settings.APP_VERSION}
