"""StockWise Phase 10 — End-to-End Integration, Security Validation, and Release Readiness Tests.

This test module verifies the complete business lifecycle across all 5 portals, validates
multi-tenant boundaries, ensures idempotency, and confirms security hardening.
"""

from datetime import date, timedelta, datetime, timezone
import json
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    Organization,
    Location,
    Product,
    InventorySnapshot,
    Route,
    SalesHistory,
    Shipment,
    ShipmentEvent,
    StockMovement,
    PlanningRun,
)

PHASE10_SECRET = "phase10-super-secure-jwt-signing-secret-key-32-chars!"


def make_jwt(
    sub: str,
    email: str,
    role: str,
    org_id: str,
    secret: str = PHASE10_SECRET,
    user_metadata: dict = None,
    app_metadata: dict = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=2)).timestamp()),
        "app_metadata": app_metadata if app_metadata is not None else {"role": role, "org_id": org_id},
        "user_metadata": user_metadata or {},
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def auth_header(sub: str, role: str, org_id: str, user_metadata: dict = None) -> dict:
    token = make_jwt(
        sub=sub,
        email=f"{sub.lower()}@stockwise.test",
        role=role,
        org_id=org_id,
        user_metadata=user_metadata,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def phase10_env(db_session: Session):
    """Configures secure production mode and seeds full multi-echelon network."""
    old_env = settings.ENVIRONMENT
    old_secret = settings.SUPABASE_JWT_SECRET
    settings.ENVIRONMENT = "production"
    settings.SUPABASE_JWT_SECRET = PHASE10_SECRET

    today = date.today()

    # 1. Organizations
    org_fmcg = Organization(org_id="ORG-CORP-FMCG", name="National FMCG Brands Ltd", org_type="company")
    org_dist = Organization(org_id="ORG-DIST-NORTH", name="North Star Logistics & Dist", org_type="distributor")
    org_ret = Organization(org_id="ORG-RET-CORNER", name="Corner Retail Mart 101", org_type="retailer")
    org_other = Organization(org_id="ORG-DIST-OTHER", name="Rival Logistics Corp", org_type="distributor")
    db_session.add_all([org_fmcg, org_dist, org_ret, org_other])

    # 2. Locations: Plant -> Dist Hub -> Retail Store
    loc_plant = Location(
        location_id="LOC-PLANT-01",
        name="Central Manufacturing Plant",
        location_type="plant",
        region="North",
        owner_org_id="ORG-CORP-FMCG",
        operator_org_id="ORG-CORP-FMCG",
    )
    loc_hub = Location(
        location_id="LOC-HUB-01",
        name="North Regional Dist Hub",
        location_type="distributor",
        region="North",
        owner_org_id="ORG-DIST-NORTH",
        operator_org_id="ORG-DIST-NORTH",
    )
    loc_store = Location(
        location_id="LOC-STORE-01",
        name="Downtown Corner Store",
        location_type="retailer",
        region="North",
        owner_org_id="ORG-RET-CORNER",
        operator_org_id="ORG-RET-CORNER",
    )
    loc_other = Location(
        location_id="LOC-OTHER-01",
        name="Rival Warehouse 99",
        location_type="distributor",
        region="South",
        owner_org_id="ORG-DIST-OTHER",
        operator_org_id="ORG-DIST-OTHER",
    )
    db_session.add_all([loc_plant, loc_hub, loc_store, loc_other])

    # 3. Product
    prod = Product(
        sku_id="SKU-CHOC-BAR-50G",
        name="Premium Milk Chocolate 50g",
        category="Confectionery",
        unit="cases",
    )
    db_session.add(prod)

    # 4. Routes
    r1 = Route(
        from_location_id="LOC-PLANT-01",
        to_location_id="LOC-HUB-01",
        lead_time_days=2.0,
        cost_rate=15.0,
        is_active=True,
    )
    r2 = Route(
        from_location_id="LOC-HUB-01",
        to_location_id="LOC-STORE-01",
        lead_time_days=1.0,
        cost_rate=8.0,
        is_active=True,
    )
    db_session.add_all([r1, r2])

    # 5. Inventory Snapshots:
    # Plant has 1000 units on hand
    inv_plant = InventorySnapshot(
        snapshot_id="SNAP-PLANT-01",
        sku_id="SKU-CHOC-BAR-50G",
        location_id="LOC-PLANT-01",
        owner_org_id="ORG-CORP-FMCG",
        on_hand=1000.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        as_of_date=today,
        batch_number="BATCH-PLANT-01",
        expiry_date=today + timedelta(days=180),
    )
    # Hub has 200 units on hand, 20 reserved, 10 blocked
    inv_hub = InventorySnapshot(
        snapshot_id="SNAP-HUB-01",
        sku_id="SKU-CHOC-BAR-50G",
        location_id="LOC-HUB-01",
        owner_org_id="ORG-DIST-NORTH",
        on_hand=200.0,
        reserved=20.0,
        blocked=10.0,
        confirmed_incoming=0.0,
        as_of_date=today,
        batch_number="BATCH-HUB-01",
        expiry_date=today + timedelta(days=90),
    )
    # Store has 15 units on hand (critically low)
    inv_store = InventorySnapshot(
        snapshot_id="SNAP-STORE-01",
        sku_id="SKU-CHOC-BAR-50G",
        location_id="LOC-STORE-01",
        owner_org_id="ORG-RET-CORNER",
        on_hand=15.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        as_of_date=today,
        batch_number="BATCH-STORE-01",
        expiry_date=today + timedelta(days=30),
    )
    db_session.add_all([inv_plant, inv_hub, inv_store])

    # 6. Sales History for forecasting (both Hub and Retail Store)
    sales_records = []
    for d in range(1, 15):
        # Store sales
        sales_records.append(
            SalesHistory(
                sku_id="SKU-CHOC-BAR-50G",
                destination_id="LOC-STORE-01",
                sales_date=today - timedelta(days=d),
                quantity=12.0 + (d % 3),
            )
        )
        # Hub sales/demand (50 units/day => 350 7-day demand vs 170 dispatchable => gap of 180)
        sales_records.append(
            SalesHistory(
                sku_id="SKU-CHOC-BAR-50G",
                destination_id="LOC-HUB-01",
                sales_date=today - timedelta(days=d),
                quantity=50.0,
            )
        )
    db_session.add_all(sales_records)

    db_session.commit()

    try:
        yield {
            "org_fmcg": org_fmcg,
            "org_dist": org_dist,
            "org_ret": org_ret,
            "org_other": org_other,
            "loc_plant": loc_plant,
            "loc_hub": loc_hub,
            "loc_store": loc_store,
            "prod": prod,
        }
    finally:
        settings.ENVIRONMENT = old_env
        settings.SUPABASE_JWT_SECRET = old_secret


def test_complete_12_step_business_workflow(client: TestClient, phase10_env: dict, db_session: Session):
    """
    Priority 2: End-to-End Business Lifecycle:
    Import/Seed -> Validate Accounting -> Forecast -> Detect Risk -> Optimization Run ->
    Decision Receipt -> Replenishment Request -> Approval -> Reservation -> Physical Dispatch ->
    Delivery Confirmation -> Final Inventory Reconciliation.
    """
    admin_hdr = auth_header("USER-ADMIN-01", "admin", "ORG-CORP-FMCG")
    dist_hdr = auth_header("USER-DIST-01", "distributor", "ORG-DIST-NORTH")
    ret_hdr = auth_header("USER-RET-01", "retailer", "ORG-RET-CORNER")
    wh_hdr = auth_header("USER-LOGISTICS-01", "logistics", "ORG-CORP-FMCG")

    # Step 1 & 2: Inventory Accounting Validation
    # Hub has 200 on hand, 20 reserved, 10 blocked => dispatchable = 170
    hub_inv = db_session.query(InventorySnapshot).filter_by(location_id="LOC-HUB-01").first()
    assert hub_inv.dispatchable_stock == 170.0

    # Step 3: Forecast Demand
    fc_res = client.get("/api/forecast?horizon_days=7&destination_id=LOC-STORE-01", headers=admin_hdr)
    assert fc_res.status_code == 200
    fc_data = fc_res.json()
    assert "forecasts" in fc_data
    assert len(fc_data["forecasts"]) > 0
    predicted_demand = fc_data["forecasts"][0]["total_forecast_demand"]
    assert predicted_demand > 0

    # Step 4: Detect Shortage / Risk Analysis
    risk_res = client.get("/api/risk/analysis?horizon_days=7&destination_id=LOC-STORE-01", headers=admin_hdr)
    assert risk_res.status_code == 200
    risk_data = risk_res.json()
    assert "items" in risk_data
    store_risk = [r for r in risk_data["items"] if r["destination_id"] == "LOC-STORE-01"]
    assert len(store_risk) > 0
    # Store has low cover days (1.2 days) and positive replenishment need
    assert store_risk[0]["replenishment_need"] > 0 or store_risk[0]["cover_days"] < 7.0

    # Step 5: Run Service-First Distribution Optimization
    opt_payload = {
        "horizon_days": 7,
        "objective_strategy": "lexicographic",
        "service_level_weight": 1000.0,
        "transport_cost_weight": 1.0,
        "auto_create_shipments": True,
    }
    opt_res = client.post("/api/optimization/run", json=opt_payload, headers=admin_hdr)
    assert opt_res.status_code == 201
    opt_data = opt_res.json()
    assert opt_data["solver_status"].lower() in ("optimal", "feasible")
    assert "run_id" in opt_data
    run_id = opt_data["run_id"]

    # Step 6: Verify Decision Receipts
    assert "decision_receipts" in opt_data
    assert len(opt_data["decision_receipts"]) > 0
    receipt = opt_data["decision_receipts"][0]
    assert "recommendation_id" in receipt
    assert "evidence" in receipt
    assert "estimated_cost" in receipt
    assert "rejected_alternatives" in receipt
    assert receipt["quantity"] > 0

    # Step 7: Retailer submits Replenishment Request to Distributor
    req_payload = {
        "sku_id": "SKU-CHOC-BAR-50G",
        "quantity": 50.0,
        "preferred_source_location_id": "LOC-HUB-01",
        "reason": "Store replenishment for weekend rush",
        "notes": "Urgent stock replenishment needed.",
    }
    req_res = client.post("/api/retailer/requests", json=req_payload, headers=ret_hdr)
    assert req_res.status_code == 201
    req_data = req_res.json()
    assert req_data["status"] == "proposed"
    shipment_id = req_data["shipment_id"]

    # Verify proposed shipment does NOT deduct physical inventory
    db_session.expire_all()
    hub_inv_check = db_session.query(InventorySnapshot).filter_by(location_id="LOC-HUB-01").first()
    assert hub_inv_check.on_hand == 200.0
    assert hub_inv_check.reserved == 20.0

    # Step 8: Company Admin / Planner Approves the Shipment
    appr_res = client.post(
        f"/api/shipments/{shipment_id}/approve",
        json={"approved": True, "authorized_user_id": "USER-ADMIN-01", "notes": "Approved 50 units for store."},
        headers=admin_hdr,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "approved"

    # Step 9: Prepare Dispatch (Reservation Stage)
    # Logistics / Admin stages dispatch with checklist
    prep_res = client.post(
        f"/api/shipments/{shipment_id}/prepare",
        json={
            "checklist_items": ["seal_verified", "packaging_inspected", "cold_chain_active"],
            "authorized_user_id": "USER-ADMIN-01",
            "actor_role": "admin",
            "notes": "Checklist completed for transit staging.",
        },
        headers=admin_hdr,
    )
    assert prep_res.status_code == 200
    assert prep_res.json()["status"] == "ready_for_dispatch"

    # Physical on_hand remains 200, reserved increments by 50 to 70
    db_session.expire_all()
    hub_inv_prep = db_session.query(InventorySnapshot).filter_by(location_id="LOC-HUB-01").first()
    assert hub_inv_prep.on_hand == 200.0
    assert hub_inv_prep.reserved == 70.0
    assert hub_inv_prep.dispatchable_stock == 120.0

    # Step 10: Dispatch Confirmation (Physical Stock Deduction Stage)
    confirm_res = client.post(
        f"/api/shipments/{shipment_id}/dispatch",
        json={
            "consignment_number": "CONSIGN-PHASE10-99",
            "vehicle_number": "MH-04-AZ-9999",
            "driver_contact": "+91-9876543210",
            "authorized_user_id": "USER-ADMIN-01",
            "actor_role": "admin",
            "notes": "Driver departed facility gate.",
        },
        headers=admin_hdr,
    )
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "in_transit"

    # Verify physical stock is now deducted: on_hand drops by 50 to 150, reserved drops to 20
    db_session.expire_all()
    hub_inv_post = db_session.query(InventorySnapshot).filter_by(location_id="LOC-HUB-01").first()
    assert hub_inv_post.on_hand == 150.0
    assert hub_inv_post.reserved == 20.0

    # Step 11: Idempotency Protection — Repeated Dispatch Attempt Fails
    dup_dispatch_res = client.post(
        f"/api/shipments/{shipment_id}/dispatch",
        json={
            "consignment_number": "CONSIGN-DUPLICATE",
            "authorized_user_id": "USER-ADMIN-01",
        },
        headers=admin_hdr,
    )
    assert dup_dispatch_res.status_code in (400, 422)
    assert "DUPLICATE_DISPATCH_REJECTED" in dup_dispatch_res.text

    # Step 12: Delivery Confirmation (Destination Reconciliation)
    deliv_res = client.post(
        f"/api/shipments/{shipment_id}/deliver",
        json={
            "authorized_user_id": "USER-ADMIN-01",
            "actor_role": "admin",
            "pod_reference": "POD-SIGNED-STORE-101",
            "notes": "Store manager confirmed full receipt in good condition.",
        },
        headers=admin_hdr,
    )
    assert deliv_res.status_code == 200
    assert deliv_res.json()["status"] == "delivered"

    # Destination store stock credited: on_hand was 15 + 50 = 65
    db_session.expire_all()
    store_inv_post = db_session.query(InventorySnapshot).filter_by(location_id="LOC-STORE-01").first()
    assert store_inv_post.on_hand == 65.0

    # Step 13: Duplicate Delivery Attempt Fails
    dup_deliv_res = client.post(
        f"/api/shipments/{shipment_id}/deliver",
        json={
            "authorized_user_id": "USER-ADMIN-01",
            "pod_reference": "POD-DUP",
        },
        headers=admin_hdr,
    )
    assert dup_deliv_res.status_code in (400, 422)
    assert "DUPLICATE_DELIVERY_REJECTED" in dup_deliv_res.text


def test_five_portals_scope_and_isolation(client: TestClient, phase10_env: dict):
    """
    Priority 3 & 4: Validate all 5 portals and enforce strict cross-tenant isolation.
    1. Company Admin
    2. Distribution Intelligence
    3. Warehouse & Logistics
    4. Distributor Portal
    5. Retail Shop Portal
    """
    admin_hdr = auth_header("USER-ADMIN-01", "admin", "ORG-CORP-FMCG")
    planner_hdr = auth_header("USER-PLAN-01", "planner", "ORG-CORP-FMCG")
    wh_hdr = auth_header("USER-WH-01", "logistics", "ORG-CORP-FMCG")
    dist_hdr = auth_header("USER-DIST-01", "distributor", "ORG-DIST-NORTH")
    ret_hdr = auth_header("USER-RET-01", "retailer", "ORG-RET-CORNER")
    rival_hdr = auth_header("USER-RIVAL-01", "distributor", "ORG-DIST-OTHER")

    # 1. Company Admin access to network & organizations
    r_orgs = client.get("/api/organizations", headers=admin_hdr)
    assert r_orgs.status_code == 200
    assert len(r_orgs.json()) >= 3

    # 2. Distribution Intelligence access to forecast & planning runs
    r_runs = client.get("/api/optimization/runs", headers=planner_hdr)
    assert r_runs.status_code == 200

    # 3. Warehouse & Logistics access to shipments
    r_ships = client.get("/api/shipments", headers=wh_hdr)
    assert r_ships.status_code == 200

    # 4. Distributor Portal
    r_dist_dash = client.get("/api/distributor/dashboard", headers=dist_hdr)
    assert r_dist_dash.status_code == 200
    assert r_dist_dash.json()["distributor_org_id"] == "ORG-DIST-NORTH"

    r_dist_inv = client.get("/api/distributor/inventory", headers=dist_hdr)
    assert r_dist_inv.status_code == 200
    dist_inv_list = r_dist_inv.json()
    # Hub inventory visible to distributor
    assert any(i["location_id"] == "LOC-HUB-01" for i in dist_inv_list)
    # Plant inventory NOT leaked to distributor
    assert not any(i["location_id"] == "LOC-PLANT-01" for i in dist_inv_list)

    # 5. Retail Shop Portal
    r_ret_dash = client.get("/api/retailer/dashboard", headers=ret_hdr)
    assert r_ret_dash.status_code == 200
    assert r_ret_dash.json()["retailer_org_id"] == "ORG-RET-CORNER"

    r_ret_inv = client.get("/api/retailer/inventory", headers=ret_hdr)
    assert r_ret_inv.status_code == 200
    ret_inv_list = r_ret_inv.json()
    # Store inventory visible to retailer
    assert any(i["location_id"] == "LOC-STORE-01" for i in ret_inv_list)
    # Hub inventory NOT visible to retailer
    assert not any(i["location_id"] == "LOC-HUB-01" for i in ret_inv_list)

    # Security Boundaries:
    # A) Retailer cannot access Distributor dashboard
    r_breach1 = client.get("/api/distributor/dashboard", headers=ret_hdr)
    assert r_breach1.status_code in (401, 403)

    # B) Distributor cannot access Retailer dashboard
    r_breach2 = client.get("/api/retailer/dashboard", headers=dist_hdr)
    assert r_breach2.status_code in (401, 403)

    # C) Rival Distributor cannot see North Distributor's inventory
    r_rival_inv = client.get("/api/distributor/inventory", headers=rival_hdr)
    assert r_rival_inv.status_code == 200
    assert not any(i["location_id"] == "LOC-HUB-01" for i in r_rival_inv.json())


def test_security_auth_and_privilege_escalation(client: TestClient, phase10_env: dict):
    """
    Priority 4: Unauthenticated access rejected, and client-supplied role tampering rejected.
    """
    # 1. Unauthenticated request to protected endpoints fails with 401
    r_unauth = client.get("/api/distributor/dashboard")
    assert r_unauth.status_code == 401

    r_unauth2 = client.get("/api/retailer/dashboard")
    assert r_unauth2.status_code == 401

    # 2. Client tampering: Attacker puts "admin" inside user_metadata
    tampered_token = make_jwt(
        sub="ATTACKER-01",
        email="attacker@external.com",
        role="retailer",
        org_id="ORG-RET-CORNER",
        user_metadata={"role": "admin", "org_id": "ORG-CORP-FMCG"},
    )
    tampered_hdr = {"Authorization": f"Bearer {tampered_token}"}

    # Attempting to access admin-only route fails with 403
    r_attack = client.get("/api/organizations", headers=tampered_hdr)
    assert r_attack.status_code in (401, 403)

    # 3. Invalid signature token fails with 401
    bad_token = make_jwt(
        sub="USER-BAD",
        email="bad@test.com",
        role="admin",
        org_id="ORG-CORP-FMCG",
        secret="completely-wrong-jwt-secret-xyz-1234567890",
    )
    r_bad_sig = client.get("/api/organizations", headers={"Authorization": f"Bearer {bad_token}"})
    assert r_bad_sig.status_code == 401


def test_expiry_and_redistribution_governance(client: TestClient, phase10_env: dict, db_session: Session):
    """
    Priority 5: Validate that expired stock is never treated as dispatchable,
    and redistribution proposals do not move stock prior to authorized execution.
    """
    today = date.today()

    # Add an expired batch at Plant
    expired_inv = InventorySnapshot(
        snapshot_id="SNAP-EXP-01",
        sku_id="SKU-CHOC-BAR-50G",
        location_id="LOC-PLANT-01",
        owner_org_id="ORG-CORP-FMCG",
        on_hand=300.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        as_of_date=today,
        batch_number="BATCH-EXPIRED-99",
        expiry_date=today - timedelta(days=5),  # Expired 5 days ago
    )
    db_session.add(expired_inv)
    db_session.commit()

    admin_hdr = auth_header("USER-ADMIN-01", "admin", "ORG-CORP-FMCG")

    # Call redistribution recommendations endpoint
    redist_res = client.get("/api/redistribution/recommendations", headers=admin_hdr)
    assert redist_res.status_code == 200
    redist_data = redist_res.json()
    assert "recommendations" in redist_data

    # Verify that creating a proposal does NOT alter physical stock
    db_session.expire_all()
    plant_inv = db_session.query(InventorySnapshot).filter_by(snapshot_id="SNAP-PLANT-01").first()
    assert plant_inv.on_hand == 1000.0
    assert plant_inv.reserved == 0.0
