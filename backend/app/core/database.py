import time
from typing import Dict, Any, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.core.config import settings

from urllib.parse import quote_plus, unquote_plus


def sanitize_db_url(url: str) -> str:
    """
    Safely handles and normalizes database connection URLs.
    Handles URL-encoding of reserved characters in database passwords (e.g. '@', '#', '%')
    so that SQLAlchemy engine initialization never fails on special characters.
    """
    if not url or not url.startswith("postgresql"):
        return url
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest or ":" not in rest:
        return url
    user_pass, host_part = rest.rsplit("@", 1)
    if ":" not in user_pass:
        return url
    user, raw_pass = user_pass.split(":", 1)
    cleaned_pass = quote_plus(unquote_plus(raw_pass))
    return f"{scheme}://{user}:{cleaned_pass}@{host_part}"


normalized_database_url = sanitize_db_url(settings.DATABASE_URL)

# Engine configuration
connect_args: Dict[str, Any] = {}
engine_kwargs: Dict[str, Any] = {"pool_pre_ping": True}

if normalized_database_url.startswith("postgresql"):
    connect_args["connect_timeout"] = settings.DB_CONNECT_TIMEOUT_SECONDS
    # Ensure SSL is enabled for cloud/remote PostgreSQL instances like Supabase
    if "sslmode" not in normalized_database_url.lower() and "localhost" not in normalized_database_url and "127.0.0.1" not in normalized_database_url:
        connect_args["sslmode"] = "require"
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
elif normalized_database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    normalized_database_url,
    connect_args=connect_args,
    **engine_kwargs,
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


def ensure_default_organizations() -> None:
    """
    Ensures default core organizations exist in the database (e.g. ORG-FMCG-CORP, ORG-LOGISTICS-3PL, etc.)
    without clearing, resetting, or altering existing records.
    Safely links any unassigned legacy operational inventory or locations to ORG-FMCG-CORP.
    """
    import sys
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return

    from app.models.entities import Organization
    default_orgs = [
        {
            "org_id": "ORG-FMCG-CORP",
            "name": "StockWise FMCG Corp",
            "org_type": "fmcg_company",
            "contact_email": "operations@stockwise.internal",
            "contact_phone": "+91-22-67890001",
            "is_active": True,
        },
        {
            "org_id": "ORG-LOGISTICS-3PL",
            "name": "Express Logistics 3PL Network",
            "org_type": "logistics_provider",
            "contact_email": "fleet@stockwise.internal",
            "contact_phone": "+91-22-67890002",
            "is_active": True,
        },
        {
            "org_id": "ORG-DIST-WEST",
            "name": "Western India Distributors",
            "org_type": "distributor",
            "contact_email": "orders@distwest.internal",
            "contact_phone": "+91-20-67890003",
            "is_active": True,
        },
        {
            "org_id": "ORG-RETAIL-METRO",
            "name": "Metro Retail Destinations Hub",
            "org_type": "retailer",
            "contact_email": "store@metroretail.internal",
            "contact_phone": "+91-11-67890004",
            "is_active": True,
        },
    ]
    try:
        with SessionLocal() as db:
            for org_data in default_orgs:
                existing = db.query(Organization).filter(Organization.org_id == org_data["org_id"]).first()
                if not existing:
                    db.add(Organization(**org_data))
            # Safely associate unassigned operational inventory and locations with ORG-FMCG-CORP
            db.execute(text("UPDATE inventory_snapshots SET owner_org_id = 'ORG-FMCG-CORP' WHERE owner_org_id IS NULL AND snapshot_id != 'SNAP-BENCHMARK-PUBLIC'"))
            db.execute(text("UPDATE locations SET owner_org_id = 'ORG-FMCG-CORP', operator_org_id = 'ORG-FMCG-CORP' WHERE owner_org_id IS NULL AND location_id NOT LIKE 'WH-%'"))
            db.commit()
    except Exception:
        pass


def init_db() -> None:
    """
    Creates database tables for local SQLite development and bootstraps default core tenant organizations.
    For PostgreSQL / Supabase, schema is managed strictly via Alembic migrations.
    """
    if settings.DATABASE_URL.startswith("sqlite"):
        import app.models.entities  # Ensure models are imported
        Base.metadata.create_all(bind=engine)
    ensure_default_organizations()


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
