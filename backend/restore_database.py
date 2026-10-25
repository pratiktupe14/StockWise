"""
StockWise Database Restore Tool
Restores table data from a structured backup JSON file created by backup_database.py.
"""
import os
import sys
import json
import argparse
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, Base, engine
import app.models.entities  # Ensure all model tables are registered
from sqlalchemy import text


def parse_date_or_datetime(val_str):
    if not isinstance(val_str, str):
        return val_str
    try:
        if "T" in val_str or ":" in val_str:
            return datetime.fromisoformat(val_str)
        elif len(val_str) == 10 and val_str.count("-") == 2:
            return date.fromisoformat(val_str)
    except Exception:
        pass
    return val_str


def restore_database(backup_file: str):
    path = Path(backup_file)
    if not path.exists():
        print(f"Error: Backup file '{backup_file}' does not exist.")
        sys.exit(1)

    print("=" * 60)
    print(f" Restoring StockWise Database from: {path.name}")
    print("=" * 60)

    with open(path, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    tables_data = backup_data.get("tables", {})
    db = SessionLocal()

    # Insertion order respecting foreign keys
    dependency_order = [
        "organizations",
        "products",
        "locations",
        "routes",
        "inventory_snapshots",
        "sales_history",
        "shipments",
        "shipment_events",
        "stock_movements",
        "import_runs",
        "import_row_errors",
        "planning_runs",
        "festival_events",
        "idempotency_records",
    ]

    try:
        # Clear existing records in reverse dependency order
        print("\n1. Clearing existing records in reverse dependency order...")
        for tbl_name in reversed(dependency_order):
            if tbl_name in Base.metadata.tables:
                db.execute(text(f'DELETE FROM "{tbl_name}"'))
        db.commit()
        print("   -> Cleared existing records.")

        # Insert records in forward dependency order
        print("\n2. Inserting records from backup...")
        total_restored = 0
        for tbl_name in dependency_order:
            rows = tables_data.get(tbl_name, [])
            if not rows:
                continue

            tbl = Base.metadata.tables[tbl_name]
            for row in rows:
                cleaned_row = {}
                for col_name, val in row.items():
                    if col_name in tbl.columns:
                        col_type = tbl.columns[col_name].type
                        # Parse date/datetime types if serialized as string
                        if str(col_type).startswith("DATE") or str(col_type).startswith("DATETIME") or str(col_type).startswith("TIMESTAMP"):
                            cleaned_row[col_name] = parse_date_or_datetime(val)
                        elif isinstance(val, (list, dict)):
                            cleaned_row[col_name] = json.dumps(val) if "JSON" not in str(col_type) else val
                        else:
                            cleaned_row[col_name] = val
                db.execute(tbl.insert().values(**cleaned_row))
            db.commit()
            print(f"  [+] {tbl_name:25s} : {len(rows):5d} records restored")
            total_restored += len(rows)

        print("-" * 60)
        print(f" Database successfully restored! Total records: {total_restored}")
        print("=" * 60)
    except Exception as exc:
        db.rollback()
        print(f"Restore failed with error: {exc}")
        raise exc
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore database from JSON backup.")
    parser.add_argument("backup_file", help="Path to backup JSON file")
    args = parser.parse_args()
    restore_database(args.backup_file)
