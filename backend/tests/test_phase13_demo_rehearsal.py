"""
Phase 13 End-to-End FMCG Demo Workflow Regression Test

Validates the full 13-step FMCG distribution intelligence and inventory optimization workflow:
1. Network Inspection
2. Multi-Tier Inventory Position & Dispatchable Stock
3. Demand Forecast & Critical Stockout Detection
4. Constrained Lexicographic Optimization
5. Decision Receipt with Rejected Alternatives
6. Pre-Solver Shelf-Life Eligibility
7. Retailer Replenishment Request Creation
8. Authorized Approval
9. Staging & FEFO Reservation Accounting
10. Physical Dispatch & Source Inventory Deduction
11. Delivery Confirmation & Destination Reconciliation
12. Duplicate Operation Replay Defense (HTTP 400)
13. Lifecycle Audit Trail
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.entities import InventorySnapshot
from seed_fmcg_demo import seed_demo_data

client = TestClient(app)

ADMIN_HEADERS = {"Authorization": "Bearer demo-admin-token"}
PLANNER_HEADERS = {"Authorization": "Bearer demo-planner-token"}
LOGISTICS_HEADERS = {"Authorization": "Bearer demo-logistics-token"}
RETAILER_HEADERS = {"Authorization": "Bearer demo-retailer-token"}


@pytest.fixture(autouse=True)
def setup_demo_scenario():
    seed_demo_data(reset=True)


def test_phase13_step1_network_inspection():
    resp_loc = client.get("/api/locations", headers=ADMIN_HEADERS)
    assert resp_loc.status_code == 200
    locations = resp_loc.json()
    assert len(locations) >= 5

    resp_rt = client.get("/api/routes", headers=ADMIN_HEADERS)
    assert resp_rt.status_code == 200
    routes = resp_rt.json()
    assert len(routes) >= 6


def test_phase13_step2_inventory_dispatchable_calculation():
    resp = client.get("/api/inventory", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    snapshots = resp.json()
    assert len(snapshots) >= 9
    for inv in snapshots:
        expected = max(0.0, inv["on_hand"] - inv["reserved"] - inv["blocked"])
        assert abs(inv["dispatchable_stock"] - expected) < 1e-4


def test_phase13_step3_demand_forecast_and_stockout_risk():
    resp = client.get("/api/risk/analysis?horizon_days=7", headers=PLANNER_HEADERS)
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    target = next((i for i in items if i["sku_id"] == "SKU-GOODDAY-100" and i["destination_id"] == "LOC-STORE-METRO"), None)
    assert target is not None
    assert target["risk_level"] in ("critical", "high")
    assert target["cover_days"] < 2.0  # Critical threshold


def test_phase13_step4_and_5_optimization_and_decision_receipt():
    opt_payload = {
        "horizon_days": 7,
        "strategy": "two_stage",
        "require_batch_expiry": True,
        "min_remaining_shelf_life_days": 14,
    }
    resp = client.post("/api/optimization/run", json=opt_payload, headers=PLANNER_HEADERS)
    assert resp.status_code == 201
    data = resp.json()
    assert data["solver_status"] == "optimal"
    assert data["service_level_percent"] == 100.0

    # Decision receipt check
    receipts = data.get("decision_receipts", [])
    assert len(receipts) > 0
    rec = next((rc for rc in receipts if rc["sku_id"] == "SKU-GOODDAY-100" and rc["destination_location_id"] == "LOC-STORE-METRO"), None)
    assert rec is not None
    assert rec["source_location_id"] == "LOC-NDC-BHIWANDI"
    assert len(rec["rejected_alternatives"]) >= 2


def test_phase13_step6_near_expiry_flagging():
    resp = client.get("/api/inventory?sku_id=SKU-WINKIES-400&location_id=LOC-STORE-METRO", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) > 0
    w = records[0]
    exp_date = datetime.strptime(w["expiry_date"], "%Y-%m-%d").date()
    days_left = (exp_date - datetime.now(timezone.utc).date()).days
    assert days_left <= 14  # Ineligible for 14-day minimum shelf-life cutoff


def test_phase13_steps7_through_13_complete_execution_lifecycle():
    # 7. Retailer replenishment request
    retail_payload = {
        "sku_id": "SKU-GOODDAY-100",
        "quantity": 105.0,
        "preferred_source_location_id": "LOC-NDC-BHIWANDI",
        "reason": "Replenish stockout risk",
        "notes": "Triggered from Retail Portal",
        "required_by_date": (datetime.now(timezone.utc).date() + timedelta(days=3)).strftime("%Y-%m-%d"),
    }
    resp = client.post("/api/retailer/requests", json=retail_payload, headers=RETAILER_HEADERS)
    assert resp.status_code == 201
    shipment_id = resp.json()["shipment_id"]

    # Verify safeguard: no physical change on request
    db = SessionLocal()
    bhi_inv = db.query(InventorySnapshot).filter(
        InventorySnapshot.sku_id == "SKU-GOODDAY-100",
        InventorySnapshot.location_id == "LOC-NDC-BHIWANDI"
    ).first()
    assert bhi_inv.on_hand == 4500.0
    assert bhi_inv.reserved == 0.0
    db.close()

    # 8. Approval
    appr_payload = {
        "approved": True,
        "authorized_user_id": "USER-ADMIN-01",
        "notes": "Approved by central planning admin",
    }
    resp = client.post(f"/api/shipments/{shipment_id}/approve", json=appr_payload, headers=ADMIN_HEADERS)
    assert resp.status_code == 200

    # Assign carrier
    carrier_payload = {
        "carrier_agency_id": "ORG-LOGISTICS-3PL",
        "carrier_contact": "dispatch@tci-bluedart.internal",
        "authorized_user_id": "USER-ADMIN-01",
    }
    resp = client.post(f"/api/shipments/{shipment_id}/assign-carrier", json=carrier_payload, headers=ADMIN_HEADERS)
    assert resp.status_code == 200

    # 9. Prepare / Stage
    prep_payload = {
        "authorized_user_id": "USER-LOGISTICS-01",
        "actor_role": "warehouse_supervisor",
        "checklist_items": ["packaging_inspected", "quantity_reconciled"],
        "notes": "Staged for dispatch",
    }
    resp = client.post(f"/api/shipments/{shipment_id}/prepare", json=prep_payload, headers=LOGISTICS_HEADERS)
    assert resp.status_code == 200

    # Verify reservation accounting
    db = SessionLocal()
    bhi_inv = db.query(InventorySnapshot).filter(
        InventorySnapshot.sku_id == "SKU-GOODDAY-100",
        InventorySnapshot.location_id == "LOC-NDC-BHIWANDI"
    ).first()
    assert bhi_inv.on_hand == 4500.0
    assert bhi_inv.reserved == 105.0
    assert bhi_inv.dispatchable_stock == 4395.0
    db.close()

    # 10. Dispatch
    disp_payload = {
        "authorized_user_id": "USER-LOGISTICS-01",
        "actor_role": "warehouse_manager",
        "consignment_number": "CN-TEST-001",
        "vehicle_number": "MH-04-AB-1234",
    }
    resp = client.post(f"/api/shipments/{shipment_id}/dispatch", json=disp_payload, headers=LOGISTICS_HEADERS)
    assert resp.status_code == 200

    # Verify physical inventory deduction
    db = SessionLocal()
    bhi_inv = db.query(InventorySnapshot).filter(
        InventorySnapshot.sku_id == "SKU-GOODDAY-100",
        InventorySnapshot.location_id == "LOC-NDC-BHIWANDI"
    ).first()
    assert bhi_inv.on_hand == 4395.0
    assert bhi_inv.reserved == 0.0
    db.close()

    # 11. Delivery confirmation & Destination reconciliation
    deliv_payload = {
        "authorized_user_id": "USER-LOGISTICS-01",
        "actor_role": "receiving_officer",
        "pod_reference": "POD-STORE-101",
    }
    resp = client.post(f"/api/shipments/{shipment_id}/deliver", json=deliv_payload, headers=LOGISTICS_HEADERS)
    assert resp.status_code == 200

    # Verify destination credited exactly once
    db = SessionLocal()
    dest_inv = db.query(InventorySnapshot).filter(
        InventorySnapshot.sku_id == "SKU-GOODDAY-100",
        InventorySnapshot.location_id == "LOC-STORE-METRO"
    ).first()
    assert dest_inv.on_hand == 140.0  # 35 initial + 105 received
    db.close()

    # 12. Duplicate replay rejection
    dup_resp = client.post(f"/api/shipments/{shipment_id}/deliver", json=deliv_payload, headers=LOGISTICS_HEADERS)
    assert dup_resp.status_code == 400
    assert "DUPLICATE_DELIVERY_REJECTED" in dup_resp.json().get("detail", "")

    # 13. Audit events trail
    resp_ev = client.get(f"/api/shipments/{shipment_id}/events", headers=ADMIN_HEADERS)
    assert resp_ev.status_code == 200
    events = resp_ev.json()
    assert len(events) >= 5
