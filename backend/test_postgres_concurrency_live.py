"""
StockWise — Live PostgreSQL Concurrency & Transactional Integrity Test Suite.

Executes real concurrent multi-session transactions directly against the live PostgreSQL database:
1. Concurrent race for limited inventory (over-allocation protection).
2. Concurrent double-dispatch attempts (idempotency and state machine serialization).
3. Concurrent double-delivery attempts (destination double-crediting protection).
4. Concurrent idempotency replay and conflict detection.
5. Transaction rollback integrity.

STRICT SAFETY:
- Uses isolated synthetic identifiers with UUID prefix (TEST-CONC-<UUID>).
- Cleans up all created rows in finally block.
- Never touches real or existing production data.
"""

import sys
import os
import uuid
import time
from datetime import datetime, timezone, date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.database import engine, SessionLocal
from app.models.entities import (
    Organization,
    Location,
    Product,
    InventorySnapshot,
    Shipment,
    ShipmentEvent,
    StockMovement,
    IdempotencyRecord,
    utcnow,
)
from app.services.logistics_service import prepare_dispatch, confirm_dispatch, confirm_delivery
from app.schemas.logistics import (
    ShipmentDispatchPrepareRequest,
    ShipmentDispatchConfirmRequest,
    ShipmentDeliveryConfirmRequest,
)
from app.services.idempotency_service import check_idempotency, record_idempotency
from fastapi import HTTPException


def run_live_postgres_concurrency():
    print("=" * 70)
    print("StockWise Live PostgreSQL Concurrency & Inventory Integrity Suite")
    print("=" * 70)

    dialect = engine.dialect.name
    print(f"Connected dialect: {dialect}")
    if dialect != "postgresql":
        print(f"SKIPPING: Dialect is '{dialect}'. This live concurrency suite requires PostgreSQL.")
        return False, "Not PostgreSQL"

    run_id = uuid.uuid4().hex[:6].upper()
    print(f"Execution Tag: TEST-CONC-{run_id}")

    test_org_id = f"ORG-CONC-{run_id}"
    test_src_loc = f"LOC-SRC-{run_id}"
    test_dst_loc = f"LOC-DST-{run_id}"
    test_sku_id = f"SKU-CONC-{run_id}"
    today = date.today()

    db = SessionLocal()
    try:
        # Setup test master data
        org = Organization(org_id=test_org_id, name=f"Test Concurrency Org {run_id}", org_type="company")
        loc_src = Location(
            location_id=test_src_loc,
            name="Source DC",
            location_type="plant",
            region="North",
            owner_org_id=test_org_id,
            operator_org_id=test_org_id,
        )
        loc_dst = Location(
            location_id=test_dst_loc,
            name="Dest DC",
            location_type="retailer",
            region="North",
            owner_org_id=test_org_id,
            operator_org_id=test_org_id,
        )
        prod = Product(sku_id=test_sku_id, name="Concurrency Test Bar", category="Test", unit="cases")

        # 100 units on hand at source
        inv_src = InventorySnapshot(
            snapshot_id=f"SNAP-SRC-{run_id}",
            sku_id=test_sku_id,
            location_id=test_src_loc,
            owner_org_id=test_org_id,
            on_hand=100.0,
            reserved=0.0,
            blocked=0.0,
            as_of_date=today,
            batch_number=f"BATCH-CONC-{run_id}",
            expiry_date=today + timedelta(days=60),
        )
        db.add_all([org, loc_src, loc_dst, prod, inv_src])
        db.commit()
        print("Test fixture seeded successfully.")

        # =====================================================================
        # SCENARIO 1: Concurrent Reservation for Limited Stock
        # Two shipments need 70 units each. Total available is only 100 units.
        # =====================================================================
        print("\n[Scenario 1] Concurrent Reservation / Prepare Dispatch for Limited Stock...")
        shp1_id = f"SHP-C1-{run_id}"
        shp2_id = f"SHP-C2-{run_id}"

        shp1 = Shipment(
            shipment_id=shp1_id,
            sku_id=test_sku_id,
            quantity=70.0,
            source_location_id=test_src_loc,
            destination_location_id=test_dst_loc,
            owner_org_id=test_org_id,
            status="approved",
            approval_status="approved",
        )
        shp2 = Shipment(
            shipment_id=shp2_id,
            sku_id=test_sku_id,
            quantity=70.0,
            source_location_id=test_src_loc,
            destination_location_id=test_dst_loc,
            owner_org_id=test_org_id,
            status="approved",
            approval_status="approved",
        )
        db.add_all([shp1, shp2])
        db.commit()

        def worker_reserve(shipment_id: str):
            thread_db = SessionLocal()
            try:
                req = ShipmentDispatchPrepareRequest(
                    authorized_user_id="USER-TEST",
                    actor_role="logistics",
                    checklist_items=["seal_verified", "dock_assigned"],
                    notes="Concurrent prepare worker",
                )
                res = prepare_dispatch(thread_db, shipment_id, req)
                return {"status": "SUCCESS", "shipment_id": shipment_id}
            except HTTPException as e:
                return {"status": "FAILED", "code": e.status_code, "detail": str(e.detail)}
            finally:
                thread_db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker_reserve, shp1_id)
            f2 = executor.submit(worker_reserve, shp2_id)
            results1 = [f1.result(), f2.result()]

        success_count = sum(1 for r in results1 if r["status"] == "SUCCESS")
        failure_count = sum(1 for r in results1 if r["status"] == "FAILED")
        print(f" -> Results: {success_count} succeeded, {failure_count} failed")
        assert success_count == 1, f"Expected exactly 1 reservation to succeed, got {success_count}"
        assert failure_count == 1, f"Expected exactly 1 reservation to fail, got {failure_count}"

        # Verify database state
        db.expire_all()
        check_inv = db.query(InventorySnapshot).filter_by(snapshot_id=f"SNAP-SRC-{run_id}").first()
        print(f" -> Verified Stock: on_hand={check_inv.on_hand}, reserved={check_inv.reserved}, dispatchable={check_inv.dispatchable_stock}")
        assert check_inv.on_hand == 100.0
        assert check_inv.reserved == 70.0
        assert check_inv.dispatchable_stock == 30.0
        assert check_inv.dispatchable_stock >= 0.0
        print(" [PASS] Concurrent reservation preserved inventory integrity and serialized correctly via FOR UPDATE.")

        # Determine which shipment succeeded for Scenario 2
        active_shp_id = shp1_id if results1[0]["status"] == "SUCCESS" else shp2_id

        # =====================================================================
        # SCENARIO 2: Concurrent Double-Dispatch on the Same Shipment
        # =====================================================================
        print("\n[Scenario 2] Concurrent Double-Dispatch on the Same Shipment...")

        def worker_dispatch(shipment_id: str, vehicle: str):
            thread_db = SessionLocal()
            try:
                req = ShipmentDispatchConfirmRequest(
                    authorized_user_id="USER-DISPATCH",
                    actor_role="logistics",
                    consignment_number=f"CONSIGN-{vehicle}",
                    vehicle_number=vehicle,
                    notes="Concurrent dispatch attempt",
                )
                res = confirm_dispatch(thread_db, shipment_id, req)
                return {"status": "SUCCESS", "shipment_id": shipment_id}
            except HTTPException as e:
                return {"status": "FAILED", "code": e.status_code, "detail": str(e.detail)}
            finally:
                thread_db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            f_disp1 = executor.submit(worker_dispatch, active_shp_id, "TRUCK-A")
            f_disp2 = executor.submit(worker_dispatch, active_shp_id, "TRUCK-B")
            results2 = [f_disp1.result(), f_disp2.result()]

        disp_success = sum(1 for r in results2 if r["status"] == "SUCCESS")
        disp_failure = sum(1 for r in results2 if r["status"] == "FAILED")
        print(f" -> Results: {disp_success} succeeded, {disp_failure} failed")
        assert disp_success == 1, f"Expected exactly 1 dispatch to succeed, got {disp_success}"
        assert disp_failure == 1, f"Expected exactly 1 dispatch to fail, got {disp_failure}"

        failed_detail = [r["detail"] for r in results2 if r["status"] == "FAILED"][0]
        assert "DUPLICATE_DISPATCH_REJECTED" in failed_detail or "INVALID_STATE_TRANSITION" in failed_detail

        db.expire_all()
        check_inv2 = db.query(InventorySnapshot).filter_by(snapshot_id=f"SNAP-SRC-{run_id}").first()
        print(f" -> Verified Stock: on_hand={check_inv2.on_hand}, reserved={check_inv2.reserved}")
        assert check_inv2.on_hand == 30.0  # 100 - 70 = 30
        assert check_inv2.reserved == 0.0  # reservation released

        movements = db.query(StockMovement).filter_by(shipment_id=active_shp_id, movement_type="actual_dispatch").all()
        assert len(movements) == 1, f"Expected exactly 1 actual_dispatch movement, got {len(movements)}"
        print(" [PASS] Concurrent double-dispatch prevented double deduction and duplicate movements.")

        # =====================================================================
        # SCENARIO 3: Concurrent Double-Delivery on the Same Shipment
        # =====================================================================
        print("\n[Scenario 3] Concurrent Double-Delivery Confirmation...")

        def worker_delivery(shipment_id: str, pod: str):
            thread_db = SessionLocal()
            try:
                req = ShipmentDeliveryConfirmRequest(
                    authorized_user_id="USER-RECEIVER",
                    actor_role="logistics",
                    pod_reference=pod,
                    notes="Concurrent delivery attempt",
                )
                res = confirm_delivery(thread_db, shipment_id, req)
                return {"status": "SUCCESS", "shipment_id": shipment_id}
            except HTTPException as e:
                return {"status": "FAILED", "code": e.status_code, "detail": str(e.detail)}
            finally:
                thread_db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            f_del1 = executor.submit(worker_delivery, active_shp_id, "POD-01")
            f_del2 = executor.submit(worker_delivery, active_shp_id, "POD-02")
            results3 = [f_del1.result(), f_del2.result()]

        del_success = sum(1 for r in results3 if r["status"] == "SUCCESS")
        del_failure = sum(1 for r in results3 if r["status"] == "FAILED")
        print(f" -> Results: {del_success} succeeded, {del_failure} failed")
        assert del_success == 1, f"Expected exactly 1 delivery to succeed, got {del_success}"
        assert del_failure == 1, f"Expected exactly 1 delivery to fail, got {del_failure}"

        db.expire_all()
        dest_inv = db.query(InventorySnapshot).filter_by(
            sku_id=test_sku_id,
            location_id=test_dst_loc,
        ).first()
        print(f" -> Destination Stock: on_hand={dest_inv.on_hand if dest_inv else 0}")
        assert dest_inv is not None
        assert dest_inv.on_hand == 70.0  # Credited exactly once
        print(" [PASS] Concurrent delivery prevented double crediting at destination facility.")

        # =====================================================================
        # SCENARIO 4: Idempotency Key Replay and Conflict
        # =====================================================================
        print("\n[Scenario 4] Idempotency Key Replay & Conflict...")
        idem_key = f"IDEM-KEY-{run_id}"
        payload_orig = {"shipment_id": active_shp_id, "qty": 70}
        payload_alt = {"shipment_id": active_shp_id, "qty": 999}

        record_idempotency(
            db=db,
            key=idem_key,
            user_id="USER-TEST",
            endpoint="/api/test/idempotent",
            request_payload=payload_orig,
            status_code=200,
            response_data={"status": "confirmed", "qty": 70},
        )

        # Replay identical payload -> returns cached 200
        replay = check_idempotency(db, key=idem_key, endpoint="/api/test/idempotent", request_payload=payload_orig)
        assert replay is not None
        assert replay[0] == 200
        assert replay[1]["status"] == "confirmed"

        # Conflicting payload with same key -> 409 Conflict
        try:
            check_idempotency(db, key=idem_key, endpoint="/api/test/idempotent", request_payload=payload_alt)
            assert False, "Expected 409 Conflict on altered payload"
        except HTTPException as he:
            assert he.status_code == 409
            print(f" -> Verified 409 Conflict detail: {he.detail}")
        print(" [PASS] Idempotency service correctly replays identical requests and rejects hash mismatches.")

        # =====================================================================
        # SCENARIO 5: Transaction Rollback Integrity
        # =====================================================================
        print("\n[Scenario 5] Transaction Rollback on Error...")
        shp_rb_id = f"SHP-RB-{run_id}"
        shp_rb = Shipment(
            shipment_id=shp_rb_id,
            sku_id=test_sku_id,
            quantity=20.0,
            source_location_id=test_src_loc,
            destination_location_id=test_dst_loc,
            owner_org_id=test_org_id,
            status="proposed",  # Status is proposed, not approved!
            approval_status="pending",
        )
        db.add(shp_rb)
        db.commit()

        # Attempt to prepare dispatch on unapproved shipment -> should fail and rollback
        try:
            req_invalid = ShipmentDispatchPrepareRequest(
                authorized_user_id="USER-RB",
                actor_role="logistics",
                checklist_items=["seal_verified"],
            )
            prepare_dispatch(db, shp_rb_id, req_invalid)
            assert False, "Expected failure on unapproved shipment"
        except HTTPException as he:
            assert he.status_code == 400
            db.rollback()

        db.expire_all()
        # Verify shipment status is still proposed, no movements created
        check_rb = db.query(Shipment).filter_by(shipment_id=shp_rb_id).first()
        assert check_rb.status == "proposed"
        rb_movs = db.query(StockMovement).filter_by(shipment_id=shp_rb_id).all()
        assert len(rb_movs) == 0
        print(" [PASS] Failed operations roll back completely without partial mutations.")

        print("\nALL 5 LIVE POSTGRESQL CONCURRENCY SCENARIOS PASSED WITH ZERO INTEGRITY ANOMALIES!")
        return True, "All 5 PostgreSQL Concurrency Scenarios Passed"

    finally:
        # Cleanup synthetic test entities
        print("\nCleaning up synthetic test fixtures...")
        try:
            with engine.connect() as conn:
                conn.execute(IdempotencyRecord.__table__.delete().where(IdempotencyRecord.key.like(f"%{run_id}%")))
                conn.execute(ShipmentEvent.__table__.delete().where(ShipmentEvent.shipment_id.like(f"%{run_id}%")))
                conn.execute(StockMovement.__table__.delete().where(StockMovement.shipment_id.like(f"%{run_id}%")))
                conn.execute(Shipment.__table__.delete().where(Shipment.shipment_id.like(f"%{run_id}%")))
                conn.execute(InventorySnapshot.__table__.delete().where(InventorySnapshot.sku_id == test_sku_id))
                conn.execute(Product.__table__.delete().where(Product.sku_id == test_sku_id))
                conn.execute(Location.__table__.delete().where(Location.location_id.in_([test_src_loc, test_dst_loc])))
                conn.execute(Organization.__table__.delete().where(Organization.org_id == test_org_id))
                conn.commit()
            print("Cleanup complete.")
        except Exception as ce:
            print(f"Cleanup warning: {ce}")
        db.close()


if __name__ == "__main__":
    success, msg = run_live_postgres_concurrency()
    sys.exit(0 if success else 1)
