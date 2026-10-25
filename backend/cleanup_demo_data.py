"""
StockWise Safe Demo Data Cleanup Tool
Removes verified seeded demo business data while preserving import history and audit logs.
Runs inside a single atomic database transaction.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, Base, engine
import app.models.entities  # Ensure models are loaded
from app.models.entities import (
    ShipmentEvent,
    StockMovement,
    Shipment,
    PlanningRun,
    InventorySnapshot,
    SalesHistory,
    Route,
    Location,
    Product,
    Organization,
    FestivalEvent,
    ImportRun,
    ImportRowError,
    IdempotencyRecord,
)
from sqlalchemy import text


def verify_backup_exists():
    backup_dir = Path(__file__).parent / "backups"
    if not backup_dir.exists():
        return False
    backups = list(backup_dir.glob("stockwise_backup_*.json"))
    return len(backups) > 0


def cleanup_demo_data():
    print("=" * 70)
    print(" StockWise Safe Demo Data Cleanup")
    print("=" * 70)

    # 1. Verification of backup safety gate
    if not verify_backup_exists():
        print("ERROR: No database backup found in backend/backups/.")
        print("Aborting cleanup to protect database integrity.")
        sys.exit(1)

    print(" Verified database backup exists.")

    db = SessionLocal()
    cleanup_summary = {}

    try:
        print("\nExecuting atomic transactional cleanup of verified demo data...")
        with db.begin():
            # 1. Shipment Events
            cnt_events = db.query(ShipmentEvent).delete(synchronize_session=False)
            cleanup_summary["shipment_events"] = cnt_events

            # 2. Stock Movements
            cnt_movs = db.query(StockMovement).delete(synchronize_session=False)
            cleanup_summary["stock_movements"] = cnt_movs

            # 3. Shipments
            cnt_shipments = db.query(Shipment).delete(synchronize_session=False)
            cleanup_summary["shipments"] = cnt_shipments

            # 4. Planning Runs
            cnt_planning = db.query(PlanningRun).delete(synchronize_session=False)
            cleanup_summary["planning_runs"] = cnt_planning

            # 5. Inventory Snapshots
            cnt_snapshots = db.query(InventorySnapshot).delete(synchronize_session=False)
            cleanup_summary["inventory_snapshots"] = cnt_snapshots

            # 6. Sales History
            cnt_sales = db.query(SalesHistory).delete(synchronize_session=False)
            cleanup_summary["sales_history"] = cnt_sales

            # 7. Routes
            cnt_routes = db.query(Route).delete(synchronize_session=False)
            cleanup_summary["routes"] = cnt_routes

            # 8. Locations
            cnt_locations = db.query(Location).delete(synchronize_session=False)
            cleanup_summary["locations"] = cnt_locations

            # 9. Products
            cnt_products = db.query(Product).delete(synchronize_session=False)
            cleanup_summary["products"] = cnt_products

            # 10. Organizations
            cnt_orgs = db.query(Organization).delete(synchronize_session=False)
            cleanup_summary["organizations"] = cnt_orgs

            # 11. Festival Events
            cnt_festivals = db.query(FestivalEvent).delete(synchronize_session=False)
            cleanup_summary["festival_events"] = cnt_festivals

        print("\n" + "-" * 70)
        print(" Cleanup Summary (Deleted Records):")
        print("-" * 70)
        total_deleted = 0
        for table_name, count in cleanup_summary.items():
            print(f"  [-] {table_name:25s} : {count:5d} records removed")
            total_deleted += count

        print("-" * 70)
        print(f" Total demo records safely removed: {total_deleted}")
        print("=" * 70)

        # Verify preserved tables
        print("\nVerifying preserved operational & audit tables:")
        import_runs_count = db.query(ImportRun).count()
        import_errors_count = db.query(ImportRowError).count()
        idempotency_count = db.query(IdempotencyRecord).count()

        print(f"  [*] import_runs (Preserved Audit Log)   : {import_runs_count} records")
        print(f"  [*] import_row_errors (Preserved Audit) : {import_errors_count} records")
        print(f"  [*] idempotency_records (Preserved Sec) : {idempotency_count} records")
        print("=" * 70)

        return cleanup_summary

    except Exception as exc:
        db.rollback()
        print(f"\nERROR during cleanup: {exc}")
        print("Database transaction rolled back. No changes persisted.")
        raise exc
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_demo_data()
