from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

# Base class for models - can be imported without connecting to DB
Base = declarative_base()

# Engine and SessionLocal are lazily created
_engine = None
_SessionLocal = None


def get_engine():
    """
    Lazy engine creation - only connects when first used.
    This prevents import-time failures if database is unreachable.
    """
    global _engine
    if _engine is None:
        from app.core.config import settings
        logger.info(f"Creating database engine for: {settings.DATABASE_URL[:50]}...")
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            # Connection timeout to avoid hanging forever
            connect_args={"connect_timeout": 10}
        )
    return _engine


def get_session_local():
    """Get or create SessionLocal factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def get_db():
    """Dependency to get database session."""
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """
    Check if database is reachable.
    Returns True if connected, False otherwise.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


# For backwards compatibility - expose engine property
# But use lazy initialization
@property
def engine():
    return get_engine()
