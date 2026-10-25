"""
StockWise Database Backup Tool
Exports all table data from the live database into a structured, timestamped JSON snapshot.
Can be restored via restore_database.py.
"""
import os
import sys
import json
from datetime import datetime, date, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, Base, engine
import app.models.entities  # Ensure all model tables are registered
from sqlalchemy import text


def serialize_val(val):
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, (int, float, bool, str, list, dict)):
        return val
    return str(val)


def backup_database():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(__file__).parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"stockwise_backup_{timestamp}.json"

    print("=" * 60)
    print(f" Starting StockWise Database Backup: {timestamp}")
    print("=" * 60)

    db = SessionLocal()
    backup_data = {
        "timestamp": timestamp,
        "database_dialect": engine.dialect.name,
        "tables": {},
    }

    try:
        table_names = list(Base.metadata.tables.keys())
        total_records = 0

        for tbl_name in table_names:
            result = db.execute(text(f'SELECT * FROM "{tbl_name}"')).mappings().all()
            rows = []
            for row in result:
                rows.append({k: serialize_val(v) for k, v in row.items()})
            backup_data["tables"][tbl_name] = rows
            count = len(rows)
            total_records += count
            print(f"  [+] {tbl_name:25s} : {count:5d} records backed up")

        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2)

        print("-" * 60)
        print(f" Backup successfully written to:")
        print(f"   {backup_path}")
        print(f" Total records saved across {len(table_names)} tables: {total_records}")
        print("=" * 60)
        return str(backup_path)
    finally:
        db.close()


if __name__ == "__main__":
    backup_database()
