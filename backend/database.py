"""
VYAS v2.0 — Database Configuration
=====================================
Connection pooling configured for production PostgreSQL.
SQLite still works for local dev but is explicitly discouraged.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dotenv import load_dotenv
load_dotenv()

from core.config import get_settings

settings = get_settings()
DATABASE_URL = settings.DATABASE_URL

_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    connect_args = {}
    if DATABASE_URL.startswith("postgresql+psycopg"):
        connect_args["prepare_threshold"] = None

    engine = create_engine(
        DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=True,
        echo=settings.DEBUG,
        connect_args=connect_args,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency: yields a DB session and ensures it is always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
