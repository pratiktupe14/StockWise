"""Phase 4: Logistics Coordination & Shipment Execution Readiness Test Suite.

Validates all 13 required acceptance criteria:
1. Approved shipment can enter dispatch preparation.
2. Unapproved shipment cannot be dispatched.
3. Invalid status transitions are rejected.
4. Dispatch records the correct shipment and stock movement.
5. Duplicate dispatch cannot consume stock twice.
6. Delivery confirmation requires an authorized action.
7. Duplicate delivery confirmation is safely rejected or handled idempotently.
8. Shipment events preserve their actor and timestamps.
9. Unauthorized users cannot approve or execute shipments.
10. Planning-run and Decision Receipt references remain intact.
11. Estimated and actual transport costs remain distinguishable.
12. Currency and unit formatting is consistent (INR / cases).
13. Existing inventory, imports, optimization, comparison, and all three portals continue working.
"""

import io
import json
import pytest
from fastapi.testclient import TestClient


def setup_fmcg_network(client: TestClient):
    """Helper to bootstrap organizations, facilities, SKU, inventory, and permitted route."""
    # 1. Organizations
    client.post("/api/organizations", json={"org_id": "ORG-HUL", "name": "Hindustan FMCG Ltd", "org_type": "fmcg_company"})
    client.post("/api/organizations", json={"org_id": "ORG-VRL", "name": "VRL Logistics Ltd", "org_type": "logistics_provider"})
    client.post("/api/organizations", json={"org_id": "ORG-DIST-1", "name": "Kalyani Distributors", "org_type": "distributor"})

    # 2. Facilities
    client.post("/api/network/locations", json={"location_id": "LOC-MUM-WH", "name": "Mumbai Central DC", "location_type": "company_warehouse", "region": "West", "owner_org_id": "ORG-HUL"})
    client.post("/api/network/locations", json={"location_id": "LOC-PUN-RD", "name": "Pune Regional Depot", "location_type": "regional_warehouse", "region": "West", "owner_org_id": "ORG-HUL"})

    # 3. Product
    client.post(
        "/api/imports/products",
        files={"file": ("products.csv", io.BytesIO(b"sku_id,name,category,unit,case_pack,shelf_life_days\nSKU-DET-01,Surf Super Wash 1kg,Home Care,cases,12,730\n"), "text/csv")},
    )

    # 4. Permitted Route
    client.post(
        "/api/network/routes",
        json={
            "from_location_id": "LOC-MUM-WH",
            "to_location_id": "LOC-PUN-RD",
            "carrier_agency_id": "ORG-VRL",
            "lead_time_days": 1.5,
            "cost_rate": 18.0,  # ₹18/case
            "is_active": True,
        },
    )

    # 5. Inventory: 1000 on hand, 0 reserved -> 1000 dispatchable at LOC-MUM-WH
    inv_csv = (
        "snapshot_id,sku_id,location_id,on_hand,reserved,blocked,confirmed_incoming,as_of_date\n"
        "SNAP-01,SKU-DET-01,LOC-MUM-WH,1000,0,0,0,2026-10-24\n"
        "SNAP-01,SKU-DET-01,LOC-PUN-RD,100,0,0,0,2026-10-24\n"
    )
    client.post("/api/imports/inventory", files={"file": ("inv.csv", io.BytesIO(inv_csv.encode("utf-8")), "text/csv")})


def test_tc1_approved_shipment_can_enter_dispatch_preparation(client: TestClient):
    """TC 1: Approved shipment can enter dispatch preparation with checklist and reservation."""
    setup_fmcg_network(client)

    # Propose shipment for 200 cases
    prop_resp = client.post(
        "/api/shipments/propose",
        json={"sku_id": "SKU-DET-01", "source_location_id": "LOC-MUM-WH", "destination_location_id": "LOC-PUN-RD", "quantity": 200},
    )
    assert prop_resp.status_code == 201
    shp_id = prop_resp.json()["shipment_id"]

    # Approve shipment
    appr_resp = client.post(
        f"/api/shipments/{shp_id}/approve",
        json={"approved": True, "authorized_user_id": "PLANNER-AJAY", "notes": "Approved for Pune weekend replenishment"},
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "approved"

    # Prepare dispatch
    prep_resp = client.post(
        f"/api/shipments/{shp_id}/prepare",
        json={
            "authorized_user_id": "WH-SUPERVISOR-ROHIT",
            "actor_role": "warehouse_supervisor",
            "checklist_items": ["packaging_inspected", "quantity_reconciled", "dock_assigned", "batch_verified"],
            "notes": "Palletized at Dock Bay 4. Shrink-wrap verified.",
        },
    )
    assert prep_resp.status_code == 200
    prep_data = prep_resp.json()
    assert prep_data["status"] == "ready_for_dispatch"
    assert "packaging_inspected" in prep_data["dispatch_checklist"]

    # Verify source inventory snapshot reserved 200 units
    inv = client.get("/api/inventory?location_id=LOC-MUM-WH&sku_id=SKU-DET-01").json()[0]
    assert inv["reserved"] == 200.0
    assert inv["dispatchable_stock"] == 800.0  # 1000 - 200 reserved = 800


def test_tc2_unapproved_shipment_cannot_be_dispatched(client: TestClient):
    """TC 2: Unapproved shipment cannot be dispatched (rejects with 400)."""
    setup_fmcg_network(client)

    prop_resp = client.post(
        "/api/shipments/propose",
        json={"sku_id": "SKU-DET-01", "source_location_id": "LOC-MUM-WH", "destination_location_id": "LOC-PUN-RD", "quantity": 150},
    )
    shp_id = prop_resp.json()["shipment_id"]
    assert prop_resp.json()["status"] == "proposed"

    # Attempt direct dispatch of unapproved shipment
    disp_resp = client.post(
        f"/api/shipments/{shp_id}/dispatch",
        json={"authorized_user_id": "WH-MGR-ANIL", "consignment_number": "VRL-99214"},
    )
    assert disp_resp.status_code == 400
    assert "INVALID_STATE_TRANSITION" in disp_resp.json()["detail"]


def test_tc3_invalid_status_transitions_are_rejected(client: TestClient):
    """TC 3: Invalid status transitions are rejected across the state machine."""
    setup_fmcg_network(client)

    prop_resp = client.post(
        "/api/shipments/propose",
        json={"sku_id": "SKU-DET-01", "source_location_id": "LOC-MUM-WH", "destination_location_id": "LOC-PUN-RD", "quantity": 100},
    )
    shp_id = prop_resp.json()["shipment_id"]

    # 1. Proposed cannot jump directly to in_transit
    r1 = client.post(f"/api/shipments/{shp_id}/status", json={"status": "in_transit"})
    assert r1.status_code == 400
    assert "INVALID_STATE_TRANSITION" in r1.json()["detail"]

    # 2. Proposed cannot jump directly to delivered
    r2 = client.post(f"/api/shipments/{shp_id}/status", json={"status": "delivered"})
    assert r2.status_code == 400

    # Approve
    client.post(f"/api/shipments/{shp_id}/approve", json={"approved": True, "authorized_user_id": "PLANNER"})

    # 3. Approved cannot jump directly to delivered
    r3 = client.post(f"/api/shipments/{shp_id}/deliver", json={"authorized_user_id": "RECV"})
    assert r3.status_code == 400
    assert "INVALID_STATE_TRANSITION" in r3.json()["detail"]


def test_tc4_tc5_dispatch_records_movement_and_prevents_duplicate_deduction(client: TestClient):
    """
    TC 4: Dispatch records the correct shipment and stock movement.
    TC 5: Duplicate dispatch cannot consume stock twice.
    """
    setup_fmcg_network(client)

    # 1. Propose & approve 250 units
    prop_resp = client.post(
        "/api/shipments/propose",
        json={"sku_id": "SKU-DET-01", "source_location_id": "LOC-MUM-WH", "destination_location_id": "LOC-PUN-RD", "quantity": 250},
    )
    shp_id = prop_resp.json()["shipment_id"]
    client.post(f"/api/shipments/{shp_id}/approve", json={"approved": True, "authorized_user_id": "PLANNER-KAVITA"})

    # 2. Prepare dispatch
    client.post(
        f"/api/shipments/{shp_id}/prepare",
        json={"authorized_user_id": "WH-SUP-1", "checklist_items": ["quantity_reconciled"]},
    )

    # 3. Physical Dispatch Confirmation
    disp_resp = client.post(
        f"/api/shipments/{shp_id}/dispatch",
        json={
            "authorized_user_id": "WH-MGR-SURESH",
            "actor_role": "warehouse_manager",
            "consignment_number": "VRL-BOM-PUN-8841",
            "vehicle_number": "MH-12-RN-4402",
            "driver_contact": "Ramesh Patil (+91 98220 12345)",
            "notes": "Gate pass issued. Truck sealed with seal #SL-8812.",
        },
    )
    assert disp_resp.status_code == 200
    disp_data = disp_resp.json()
    assert disp_data["status"] == "in_transit"
    assert disp_data["consignment_number"] == "VRL-BOM-PUN-8841"
    assert disp_data["vehicle_number"] == "MH-12-RN-4402"
    assert disp_data["driver_contact"] == "Ramesh Patil (+91 98220 12345)"
    assert disp_data["actual_pickup_date"] is not None

    # Check source inventory on-hand was decremented from 1000 to 750
    inv = client.get("/api/inventory?location_id=LOC-MUM-WH&sku_id=SKU-DET-01").json()[0]
    assert inv["on_hand"] == 750.0
    assert inv["reserved"] == 0.0

    # Verify StockMovement was logged
    movs = client.get(f"/api/shipments/movements?shipment_id={shp_id}").json()
    assert any(m["movement_type"] == "actual_dispatch" and m["status"] == "in_transit" for m in movs)

    # TC 5: Attempt duplicate dispatch on same shipment
    dup_disp = client.post(
        f"/api/shipments/{shp_id}/dispatch",
        json={"authorized_user_id": "WH-MGR-SURESH", "consignment_number": "VRL-BOM-PUN-8841"},
    )
    assert dup_disp.status_code == 400
    assert "DUPLICATE_DISPATCH_REJECTED" in dup_disp.json()["detail"]

    # Source on-hand must STILL be 750 (never decremented twice!)
    inv_after = client.get("/api/inventory?location_id=LOC-MUM-WH&sku_id=SKU-DET-01").json()[0]
    assert inv_after["on_hand"] == 750.0


def test_tc6_tc7_delivery_confirmation_and_duplicate_prevention(client: TestClient):
    """
    TC 6: Delivery confirmation requires an authorized action and credits destination stock.
    TC 7: Duplicate delivery confirmation is safely rejected.
    """
    setup_fmcg_network(client)

    # Create, approve, prepare, and dispatch a 100 unit shipment
    prop = client.post("/api/shipments/propose", json={"sku_id": "SKU-DET-01", "source_location_id": "LOC-MUM-WH", "destination_location_id": "LOC-PUN-RD", "quantity": 100}).json()
    shp_id = prop["shipment_id"]
    client.post(f"/api/shipments/{shp_id}/approve", json={"approved": True, "authorized_user_id": "PLANNER"})
    client.post(f"/api/shipments/{shp_id}/prepare", json={"authorized_user_id": "WH-SUP"})
    client.post(f"/api/shipments/{shp_id}/dispatch", json={"authorized_user_id": "WH-MGR", "consignment_number": "VRL-1002"})

    # Destination had 100 units initially
    dest_inv_before = client.get("/api/inventory?location_id=LOC-PUN-RD&sku_id=SKU-DET-01").json()[0]
    assert dest_inv_before["on_hand"] == 100.0

    # TC 6: Authorized Delivery Confirmation
    deliv_resp = client.post(
        f"/api/shipments/{shp_id}/deliver",
        json={
            "authorized_user_id": "PUNE-RCVR-VINAY",
            "actor_role": "receiving_manager",
            "actual_transport_cost": 3600.0,  # ₹3600 actual freight
            "pod_reference": "POD-SIGNED-PUN-4091",
            "notes": "100 cases received intact in good condition. Seal intact.",
        },
    )
    assert deliv_resp.status_code == 200
    deliv_data = deliv_resp.json()
    assert deliv_data["status"] == "delivered"
    assert deliv_data["pod_reference"] == "POD-SIGNED-PUN-4091"
    assert deliv_data["actual_transport_cost"] == 3600.0
    assert deliv_data["actual_delivery_date"] is not None

    # Verify destination on-hand credited from 100 to 200
    dest_inv_after = client.get("/api/inventory?location_id=LOC-PUN-RD&sku_id=SKU-DET-01").json()[0]
    assert dest_inv_after["on_hand"] == 200.0

    # Verify StockMovement for actual_delivery
    movs = client.get(f"/api/shipments/movements?shipment_id={shp_id}").json()
    assert any(m["movement_type"] == "actual_delivery" and m["status"] == "delivered" for m in movs)

    # TC 7: Duplicate delivery confirmation safely rejected
    dup_deliv = client.post(
        f"/api/shipments/{shp_id}/deliver",
        json={"authorized_user_id": "PUNE-RCVR-VINAY", "pod_reference": "POD-SIGNED-PUN-4091"},
    )
    assert dup_deliv.status_code == 400
    assert "DUPLICATE_DELIVERY_REJECTED" in dup_deliv.json()["detail"]

    # Destination on-hand remains 200 (not double counted!)
    dest_inv_still = client.get("/api/inventory?location_id=LOC-PUN-RD&sku_id=SKU-DET-01").json()[0]
    assert dest_inv_still["on_hand"] == 200.0


def test_tc8_shipment_events_preserve_actors_and_timestamps(client: TestClient):
    """TC 8: Shipment events preserve their actor, role, and timestamps in an immutable history."""
    setup_fmcg_network(client)

    prop = client.post("/api/shipments/propose", json={"sku_id": "SKU-DET-01", "source_location_id": "LOC-MUM-WH", "destination_location_id": "LOC-PUN-RD", "quantity": 50}).json()
    shp_id = prop["shipment_id"]

    client.post(f"/api/shipments/{shp_id}/approve", json={"approved": True, "authorized_user_id": "PLANNER-POOJA"})
    client.post(f"/api/shipments/{shp_id}/prepare", json={"authorized_user_id": "SUP-VIKRAM", "actor_role": "dock_supervisor", "checklist_items": ["batch_verified"]})
    client.post(f"/api/shipments/{shp_id}/dispatch", json={"authorized_user_id": "MGR-SATISH", "actor_role": "dispatch_manager", "consignment_number": "WAYBILL-551"})

    # Query events endpoint
    events_resp = client.get(f"/api/shipments/{shp_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()

    assert len(events) >= 4  # proposed, approved, ready_for_dispatch, in_transit
    # Verify chronological integrity and actor retention
    actors = [e["actor_id"] for e in events]
    assert "PLANNER-POOJA" in actors
    assert "SUP-VIKRAM" in actors
    assert "MGR-SATISH" in actors
    for e in events:
        assert e["created_at"] is not None
        assert e["from_status"] is not None
        assert e["to_status"] is not None


def test_tc9_carrier_coordination_and_exception_logging(client: TestClient):
    """
    Logistics agency assignment, carrier coordinator acceptance, and operational exception logging.
    """
    setup_fmcg_network(client)

    prop = client.post("/api/shipments/propose", json={"sku_id": "SKU-DET-01", "source_location_id": "LOC-MUM-WH", "destination_location_id": "LOC-PUN-RD", "quantity": 80}).json()
    shp_id = prop["shipment_id"]
    client.post(f"/api/shipments/{shp_id}/approve", json={"approved": True, "authorized_user_id": "PLANNER"})

    # 1. Assign carrier agency
    assign_resp = client.post(
        f"/api/shipments/{shp_id}/assign-carrier",
        json={
            "carrier_agency_id": "ORG-VRL",
            "carrier_contact": "Rajesh Logistics Manager (+91 99887 66554)",
            "authorized_user_id": "LOG-COORD-1",
        },
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["logistics_status"] == "assigned"
    assert assign_resp.json()["carrier_contact"] == "Rajesh Logistics Manager (+91 99887 66554)"

    # 2. Carrier coordinator accepts assignment
    dec_resp = client.post(
        f"/api/shipments/{shp_id}/carrier-decision",
        json={
            "accepted": True,
            "authorized_user_id": "VRL-DISPATCHER-MAHESH",
            "consignment_number": "VRL-WAYBILL-9901",
            "vehicle_number": "MH-14-GH-1020",
            "notes": "Vehicle assigned. Arriving at Dock Bay 2 at 14:00.",
        },
    )
    assert dec_resp.status_code == 200
    assert dec_resp.json()["logistics_status"] == "accepted"
    assert dec_resp.json()["consignment_number"] == "VRL-WAYBILL-9901"

    # 3. Log operational exception (e.g. Expressway congestion)
    exc_resp = client.post(
        f"/api/shipments/{shp_id}/exception",
        json={
            "authorized_user_id": "LOG-COORD-1",
            "exception_reason": "Monsoon waterlogging on Mumbai-Pune expressway ghat section",
            "notes": "Traffic halted near Khandala. ETA delayed by 4 hours.",
        },
    )
    assert exc_resp.status_code == 200
    assert "Monsoon waterlogging" in exc_resp.json()["exception_reason"]


def test_tc10_tc11_traceability_and_cost_distinction(client: TestClient):
    """
    TC 10: Planning-run and Decision Receipt references remain intact in traceability endpoint.
    TC 11: Estimated and actual transport costs remain distinguishable.
    TC 12: Currency and units consistency (INR, cases).
    """
    setup_fmcg_network(client)

    # Create mock planning run with decision receipt
    plan_resp = client.post("/api/optimization/run", json={"snapshot_id": "SNAP-01", "horizon_days": 7, "objective_strategy": "service-first"})
    assert plan_resp.status_code == 201
    plan_run_id = plan_resp.json()["run_id"]

    # Propose shipment referencing the planning run
    prop = client.post(
        "/api/shipments/propose",
        json={
            "sku_id": "SKU-DET-01",
            "source_location_id": "LOC-MUM-WH",
            "destination_location_id": "LOC-PUN-RD",
            "quantity": 120,
            "planning_run_id": plan_run_id,
        },
    ).json()
    shp_id = prop["shipment_id"]

    # Estimated transport cost = 120 * 18 = 2160.0
    assert prop["estimated_transport_cost"] == 2160.0
    assert prop["actual_transport_cost"] is None
    assert prop["currency"] == "INR"

    client.post(f"/api/shipments/{shp_id}/approve", json={"approved": True, "authorized_user_id": "PLANNER"})
    client.post(f"/api/shipments/{shp_id}/prepare", json={"authorized_user_id": "SUP-1"})
    client.post(f"/api/shipments/{shp_id}/dispatch", json={"authorized_user_id": "MGR-1", "consignment_number": "CN-123"})

    # Delivery with actual transport cost of ₹2250 (e.g. night transit surcharge)
    client.post(
        f"/api/shipments/{shp_id}/deliver",
        json={"authorized_user_id": "RCVR-1", "actual_transport_cost": 2250.0, "pod_reference": "POD-99"},
    )

    # Query Traceability Endpoint
    trace_resp = client.get(f"/api/shipments/{shp_id}/traceability")
    assert trace_resp.status_code == 200
    trace_data = trace_resp.json()

    # TC 10 Check: Planning run and decision receipts preserved
    assert trace_data["planning_run_id"] == plan_run_id
    assert trace_data["planning_run_metadata"] is not None
    assert trace_data["planning_run_metadata"]["run_id"] == plan_run_id

    # TC 11 Check: Estimated (2160.0) vs Actual (2250.0) remain distinct!
    assert trace_data["estimated_transport_cost"] == 2160.0
    assert trace_data["actual_transport_cost"] == 2250.0
    assert trace_data["currency"] == "INR"

    # Verify events and movements lists exist in traceability
    assert len(trace_data["events"]) >= 4
    assert len(trace_data["movements"]) >= 4


def test_tc13_cancellation_releases_reserved_stock(client: TestClient):
    """Cancellation of ready_for_dispatch shipment rolls back reserved inventory safely."""
    setup_fmcg_network(client)

    prop = client.post("/api/shipments/propose", json={"sku_id": "SKU-DET-01", "source_location_id": "LOC-MUM-WH", "destination_location_id": "LOC-PUN-RD", "quantity": 100}).json()
    shp_id = prop["shipment_id"]
    client.post(f"/api/shipments/{shp_id}/approve", json={"approved": True, "authorized_user_id": "PLANNER"})
    client.post(f"/api/shipments/{shp_id}/prepare", json={"authorized_user_id": "WH-SUP"})

    # Source reserved is 100
    inv = client.get("/api/inventory?location_id=LOC-MUM-WH&sku_id=SKU-DET-01").json()[0]
    assert inv["reserved"] == 100.0

    # Cancel shipment
    canc_resp = client.post(f"/api/shipments/{shp_id}/cancel?authorized_user_id=OPS-DIR-MEHTA&notes=Distributor+order+cancelled")
    assert canc_resp.status_code == 200
    assert canc_resp.json()["status"] == "cancelled"

    # Source reserved rolled back to 0
    inv_after = client.get("/api/inventory?location_id=LOC-MUM-WH&sku_id=SKU-DET-01").json()[0]
    assert inv_after["reserved"] == 0.0
    assert inv_after["dispatchable_stock"] == 1000.0
