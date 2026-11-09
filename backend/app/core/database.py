"""
SQLAlchemy database engine and session factory.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from app.core.config import settings

db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(
    db_url,
    pool_pre_ping=True,                 # Reconnect on stale connections
    pool_size=settings.DB_POOL_SIZE,    # Configurable via DB_POOL_SIZE (default 5)
    max_overflow=settings.DB_MAX_OVERFLOW, # Configurable via DB_MAX_OVERFLOW (default 5)
    pool_timeout=settings.DB_POOL_TIMEOUT, # Configurable via DB_POOL_TIMEOUT (default 30)
    pool_recycle=settings.DB_POOL_RECYCLE, # Configurable via DB_POOL_RECYCLE (default 1800)
    echo=settings.DEBUG,
    connect_args={"connect_timeout": 5},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def get_db() -> Session:
    """
    FastAPI dependency that provides a database session.
    Yields the session, then closes it after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """
    Verify that the database is reachable. Used by the health endpoint.
    Returns True if connected, False otherwise.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

