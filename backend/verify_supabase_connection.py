"""
StockWise Supabase PostgreSQL Connection & Schema Inspection Tool.
Verifies live connectivity, inspects remote tables, and checks Alembic status.
STRICT RULE: Never exposes or prints credentials, passwords, or secrets.
"""
import sys
import os

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.database import engine, check_database_connection, normalized_database_url
from sqlalchemy import inspect, text


def mask_url(url: str) -> str:
    """Masks password in URL for safe diagnostics."""
    if not url:
        return "<empty>"
    if "://" not in url:
        return "<invalid>"
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return f"{scheme}://{rest}"
    user_pass, host_part = rest.rsplit("@", 1)
    if ":" in user_pass:
        user, _ = user_pass.split(":", 1)
        return f"{scheme}://{user}:***@{host_part}"
    return f"{scheme}://***@{host_part}"


def verify_supabase():
    print("=" * 60)
    print("StockWise Supabase Verification & Schema Inspection")
    print("=" * 60)

    url = settings.DATABASE_URL
    is_placeholder = any(p in url for p in ["YOUR_DATABASE_PASSWORD", "<password>", "YOUR_PASSWORD"])
    is_postgres = url.startswith("postgresql")

    print(f"Engine target: {mask_url(normalized_database_url)}")
    print(f"Dialect: {engine.dialect.name}")
    print(f"Contains placeholder: {is_placeholder}")

    if not is_postgres:
        print("DATABASE_URL is not configured for PostgreSQL (currently SQLite/local).")
        return False, "Not PostgreSQL"

    if is_placeholder:
        print("DATABASE_URL contains placeholder. Database password has not been supplied locally.")
        return False, "Placeholder password"

    print("\nAttempting live connection query (SELECT 1)...")
    health = check_database_connection()
    if not health["connected"]:
        print(f"FAILED: {health['message']}")
        return False, health["message"]

    print(f"SUCCESS: Connected in {health['latency_ms']} ms!")

    # Inspect tables
    print("\nInspecting remote database schema...")
    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        print(f"Found {len(table_names)} tables in public schema: {table_names}")

        expected_entities = [
            "products",
            "locations",
            "inventory_snapshots",
            "sales_history",
            "routes",
            "import_runs",
            "import_row_errors",
        ]

        missing = [t for t in expected_entities if t not in table_names]
        present = [t for t in expected_entities if t in table_names]

        print(f"StockWise Phase 2 Entities present ({len(present)}/7): {present}")
        if missing:
            print(f"StockWise Phase 2 Entities missing ({len(missing)}/7): {missing}")

        # Check alembic_version
        if "alembic_version" in table_names:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
                revisions = [r[0] for r in res]
                print(f"Alembic version table found. Current revision: {revisions}")
        else:
            print("No alembic_version table found (database not yet versioned by Alembic).")

        return True, "Connected and inspected"
    except Exception as e:
        print(f"Schema inspection error: {e}")
        return False, str(e)


if __name__ == "__main__":
    success, msg = verify_supabase()
    sys.exit(0 if success else 1)
