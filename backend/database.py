"""
VYAS v2.0 — Database Configuration
=====================================
v2.0 changes:
  - Connection pooling for PostgreSQL (pool_size, max_overflow, pool_timeout)
  - SQLite stays with connect_args={"check_same_thread": False}
  - Uses AppConfig for all settings (no raw os.getenv)
  - Proper pool_pre_ping to detect stale connections
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from dotenv import load_dotenv
load_dotenv()

from config import AppConfig

DATABASE_URL = AppConfig.DATABASE_URL

# Build engine with appropriate pool settings
_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    # SQLite: no connection pooling, single-thread check disabled for FastAPI
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL / MySQL: full connection pooling
    engine = create_engine(
        DATABASE_URL,
        pool_size=AppConfig.DB_POOL_SIZE,
        max_overflow=AppConfig.DB_MAX_OVERFLOW,
        pool_timeout=AppConfig.DB_POOL_TIMEOUT,
        pool_pre_ping=True,   # detect stale connections before use
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and ensures it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
