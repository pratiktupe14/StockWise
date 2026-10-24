import time
from typing import Dict, Any, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.core.config import settings

# Engine configuration
connect_args: Dict[str, Any] = {}
if settings.DATABASE_URL.startswith("postgresql"):
    connect_args["connect_timeout"] = settings.DB_CONNECT_TIMEOUT_SECONDS

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session for requests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> Dict[str, Any]:
    """
    Verifies actual database connectivity by executing a live query.
    Returns status, latency, and informative messages without raising uncaught exceptions.
    """
    start_time = time.perf_counter()
    dialect_name = engine.dialect.name
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "connected": True,
            "message": f"Successfully connected to {dialect_name} database.",
            "dialect": dialect_name,
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        error_msg = str(exc).split("\n")[0]  # First line only for clean reporting
        return {
            "connected": False,
            "message": f"Database unreachable: {error_msg}",
            "dialect": dialect_name,
            "latency_ms": latency_ms,
        }
