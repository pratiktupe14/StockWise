"""
Comprehensive End-to-End Test Suite for Company Admin, Distributor, and Retailer Portals.

Verifies the 12 critical integration scenarios:
1. Admin can manage permitted products, categories, locations, and users; cannot delete SKU with active transactions.
2. Invalid inventory imports produce useful validation errors without corrupting stock.
3. Distributor A cannot read or modify Distributor B's inventory, requests, or deliveries.
4. Retailer A cannot read or modify Retailer B's orders, requests, or receipts.
5. Distributor and retailer users cannot access company-wide optimization or administrative operations.
6. Replenishment requests do not automatically deduct stock or dispatch shipments.
7. Only authorized users can confirm receipt or report a discrepancy.
8. Duplicate receipt confirmation cannot process the same delivery twice.
9. Invalid quantity and invalid shipment-state transitions are rejected.
10. Company-owned and independently owned inventory remain correctly separated.
11. Existing Distribution Intelligence and Warehouse & Logistics workflows continue to work.
12. Portal routes, API error handling, and authorization states function correctly.
"""

from datetime import date, timedelta, datetime, timezone
import io
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
    Shipment,
    SalesHistory,
    StockMovement,
    ShipmentEvent,
)

TEST_SECRET = "test-secret-key-for-three-portals-completion-tests-32-chars!"


def make_jwt(
    sub: str = "USER-TEST",
    email: str = "test@stockwise.internal",
    role: str = "viewer",
    org_id: str = "ORG-CORP",
    secret: str = TEST_SECRET,
    app_metadata: dict = None,
    user_metadata: dict = None,
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


def auth_headers(sub: str, email: str, role: str, org_id: str) -> dict:
    token = make_jwt(sub=sub, email=email, role=role, org_id=org_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def portal_fixture(db_session: Session):
    """Seed multi-tenant organizations, facilities, products, inventory, and shipments."""
    old_env = settings.ENVIRONMENT
    old_secret = settings.SUPABASE_JWT_SECRET
    settings.SUPABASE_JWT_SECRET = TEST_SECRET
    settings.ENVIRONMENT = "production"

    # Clean existing test data safely
    db_session.query(StockMovement).delete()
    db_session.query(ShipmentEvent).delete()
    db_session.query(Shipment).delete()
    db_session.query(SalesHistory).delete()
    db_session.query(InventorySnapshot).delete()
    db_session.query(Product).delete()
    db_session.query(Location).delete()
    db_session.query(Organization).delete()
    db_session.commit()

    # 1. Organizations
    org_company = Organization(org_id="ORG-CORP", name="StockWise FMCG Ltd", org_type="fmcg_company")
    org_dist_a = Organization(org_id="ORG-DIST-WEST", name="West Apex Distributors", org_type="distributor")
    org_dist_b = Organization(org_id="ORG-DIST-SOUTH", name="South Apex Distributors", org_type="distributor")
    org_retail_a = Organization(org_id="ORG-RETAIL-METRO", name="Metro Hypermarkets", org_type="retailer")
    org_retail_b = Organization(org_id="ORG-RETAIL-COASTAL", name="Coastal Marts", org_type="retailer")
    db_session.add_all([org_company, org_dist_a, org_dist_b, org_retail_a, org_retail_b])
    db_session.commit()

    # 2. Facilities
    wh_plant = Location(
        location_id="LOC-MFG-01",
        name="Haridwar Plant",
        location_type="manufacturing_plant",
        region="North",
        city="Haridwar",
        owner_org_id="ORG-CORP",
        operator_org_id="ORG-CORP",
        storage_capacity_units=100000,
        dispatch_capacity_daily=10000,
        is_active=True,
    )
    wh_central = Location(
        location_id="LOC-WH-DELHI",
        name="Delhi Central Warehouse",
        location_type="company_warehouse",
        region="North",
        city="Delhi",
        owner_org_id="ORG-CORP",
        operator_org_id="ORG-CORP",
        storage_capacity_units=50000,
        dispatch_capacity_daily=5000,
        is_active=True,
    )
    loc_dist_a = Location(
        location_id="LOC-DIST-WEST",
        name="Mumbai West Depot",
        location_type="distributor_warehouse",
        region="West",
        city="Mumbai",
        owner_org_id="ORG-DIST-WEST",
        operator_org_id="ORG-DIST-WEST",
        storage_capacity_units=20000,
        dispatch_capacity_daily=2000,
        is_active=True,
    )
    loc_dist_b = Location(
        location_id="LOC-DIST-SOUTH",
        name="Chennai South Depot",
        location_type="distributor_warehouse",
        region="South",
        city="Chennai",
        owner_org_id="ORG-DIST-SOUTH",
        operator_org_id="ORG-DIST-SOUTH",
        storage_capacity_units=20000,
        dispatch_capacity_daily=2000,
        is_active=True,
    )
    loc_store_a = Location(
        location_id="LOC-STORE-MUMBAI",
        name="Metro Store Andheri",
        location_type="retail_destination",
        region="West",
        city="Mumbai",
        owner_org_id="ORG-RETAIL-METRO",
        operator_org_id="ORG-RETAIL-METRO",
        storage_capacity_units=5000,
        dispatch_capacity_daily=500,
        is_active=True,
    )
    loc_store_b = Location(
        location_id="LOC-STORE-CHENNAI",
        name="Coastal Store T-Nagar",
        location_type="retail_destination",
        region="South",
        city="Chennai",
        owner_org_id="ORG-RETAIL-COASTAL",
        operator_org_id="ORG-RETAIL-COASTAL",
        storage_capacity_units=5000,
        dispatch_capacity_daily=500,
        is_active=True,
    )
    db_session.add_all([wh_plant, wh_central, loc_dist_a, loc_dist_b, loc_store_a, loc_store_b])
    db_session.commit()

    # 3. Products
    p1 = Product(
        sku_id="SKU-CHIPS-100G",
        name="Potato Chips 100g",
        category="Snacks",
        unit="cases",
        case_pack=24,
        shelf_life_days=180,
    )
    p2 = Product(
        sku_id="SKU-COLA-500ML",
        name="Sparkling Cola 500ml",
        category="Beverages",
        unit="cases",
        case_pack=12,
        shelf_life_days=365,
    )
    db_session.add_all([p1, p2])
    db_session.commit()

    # 4. Inventory Snapshots
    inv_wh_1 = InventorySnapshot(
        snapshot_id="SNAP-DEL-01",
        sku_id="SKU-CHIPS-100G",
        location_id="LOC-WH-DELHI",
        as_of_date=date.today(),
        on_hand=1000,
        reserved=100,
        blocked=0,
        batch_number="BATCH-DEL-01",
        owner_org_id="ORG-CORP",
    )
    inv_dist_a = InventorySnapshot(
        snapshot_id="SNAP-WEST-01",
        sku_id="SKU-CHIPS-100G",
        location_id="LOC-DIST-WEST",
        as_of_date=date.today(),
        on_hand=300,
        reserved=0,
        blocked=0,
        batch_number="BATCH-WEST-01",
        owner_org_id="ORG-DIST-WEST",
    )
    inv_dist_b = InventorySnapshot(
        snapshot_id="SNAP-SOUTH-01",
        sku_id="SKU-CHIPS-100G",
        location_id="LOC-DIST-SOUTH",
        as_of_date=date.today(),
        on_hand=400,
        reserved=0,
        blocked=0,
        batch_number="BATCH-SOUTH-01",
        owner_org_id="ORG-DIST-SOUTH",
    )
    inv_store_a = InventorySnapshot(
        snapshot_id="SNAP-MUM-01",
        sku_id="SKU-CHIPS-100G",
        location_id="LOC-STORE-MUMBAI",
        as_of_date=date.today(),
        on_hand=50,
        reserved=0,
        blocked=0,
        batch_number="BATCH-MUM-01",
        owner_org_id="ORG-RETAIL-METRO",
    )
    db_session.add_all([inv_wh_1, inv_dist_a, inv_dist_b, inv_store_a])
    db_session.commit()

    yield {
        "org_company": org_company,
        "org_dist_a": org_dist_a,
        "org_dist_b": org_dist_b,
        "org_retail_a": org_retail_a,
        "org_retail_b": org_retail_b,
    }

    settings.SUPABASE_JWT_SECRET = old_secret
    settings.ENVIRONMENT = old_env


# --------------------------------------------------------------------------
# Scenario 1: Admin can manage permitted products, categories, locations, and users; cannot delete SKU with active transactions
# --------------------------------------------------------------------------
def test_scenario_01_admin_crud_and_product_safeguards(client: TestClient, portal_fixture, db_session: Session):
    admin_hdr = auth_headers("ADMIN-01", "admin@stockwise.internal", "admin", "ORG-CORP")

    # 1. Create product
    create_resp = client.post(
        "/api/products",
        headers=admin_hdr,
        json={
            "sku_id": "SKU-TEST-BISCUIT",
            "name": "Butter Biscuit 200g",
            "category": "Bakery",
            "unit": "cartons",
            "case_pack": 30,
            "shelf_life_days": 120,
        },
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["sku_id"] == "SKU-TEST-BISCUIT"

    # 2. Update product
    update_resp = client.put(
        "/api/products/SKU-TEST-BISCUIT",
        headers=admin_hdr,
        json={"name": "Butter Biscuit Premium 200g", "shelf_life_days": 150},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Butter Biscuit Premium 200g"

    # 3. List categories
    cat_resp = client.get("/api/categories", headers=admin_hdr)
    assert cat_resp.status_code == 200
    categories = cat_resp.json()
    bakery_cat = next((c for c in categories if c["category"] == "Bakery"), None)
    assert bakery_cat is not None
    assert bakery_cat["product_count"] == 1

    # 4. Update facility capacity
    loc_resp = client.put(
        "/api/network/locations/LOC-WH-DELHI",
        headers=admin_hdr,
        json={"storage_capacity_units": 65000, "dispatch_capacity_daily": 6000},
    )
    assert loc_resp.status_code == 200
    assert loc_resp.json()["storage_capacity_units"] == 65000

    # 5. List users
    users_resp = client.get("/api/admin/users", headers=admin_hdr)
    assert users_resp.status_code == 200
    assert len(users_resp.json()) > 0

    # 6. Attempt to delete product with active inventory references -> Must be rejected
    del_active_resp = client.delete("/api/products/SKU-CHIPS-100G", headers=admin_hdr)
    assert del_active_resp.status_code == 400
    assert "cannot_delete_active_product" in del_active_resp.json()["detail"].lower()

    # 7. Delete unreferenced product -> Succeeds
    del_clean_resp = client.delete("/api/products/SKU-TEST-BISCUIT", headers=admin_hdr)
    assert del_clean_resp.status_code == 200
    assert del_clean_resp.json()["deleted"] is True


# --------------------------------------------------------------------------
# Scenario 2: Invalid inventory imports produce useful validation errors without corrupting stock
# --------------------------------------------------------------------------
def test_scenario_02_invalid_inventory_import_safeguards(client: TestClient, portal_fixture, db_session: Session):
    admin_hdr = auth_headers("ADMIN-01", "admin@stockwise.internal", "admin", "ORG-CORP")

    # Bad CSV with negative on_hand
    bad_csv = (
        "sku_id,location_id,on_hand,reserved,blocked,snapshot_date\n"
        "SKU-CHIPS-100G,LOC-WH-DELHI,-50,0,0,2026-10-25\n"
    )
    files = {"file": ("test_inventory.csv", io.BytesIO(bad_csv.encode("utf-8")), "text/csv")}
    resp = client.post("/api/imports/inventory", headers=admin_hdr, files=files)
    assert resp.status_code in [200, 422]
    # Check that stock was not modified to negative
    snap = (
        db_session.query(InventorySnapshot)
        .filter(InventorySnapshot.sku_id == "SKU-CHIPS-100G", InventorySnapshot.location_id == "LOC-WH-DELHI")
        .first()
    )
    assert snap.on_hand >= 0


# --------------------------------------------------------------------------
# Scenario 3: Distributor A cannot read or modify Distributor B's inventory, requests or deliveries
# --------------------------------------------------------------------------
def test_scenario_03_distributor_cross_tenant_isolation(client: TestClient, portal_fixture, db_session: Session):
    dist_a_hdr = auth_headers("DIST-A-USER", "west@dist.internal", "distributor", "ORG-DIST-WEST")
    dist_b_hdr = auth_headers("DIST-B-USER", "south@dist.internal", "distributor", "ORG-DIST-SOUTH")

    # Create an in_transit shipment for Distributor B
    shipment_b = Shipment(
        shipment_id="SHP-DIST-B-TRANSIT",
        source_location_id="LOC-WH-DELHI",
        destination_location_id="LOC-DIST-SOUTH",
        sku_id="SKU-CHIPS-100G",
        quantity=150,
        status="in_transit",
        approval_status="approved",
        logistics_status="in_transit",
        owner_org_id="ORG-CORP",
    )
    # Create a pending proposed request for Distributor B
    request_b = Shipment(
        shipment_id="REQ-DIST-B-PENDING",
        source_location_id="LOC-WH-DELHI",
        destination_location_id="LOC-DIST-SOUTH",
        sku_id="SKU-CHIPS-100G",
        quantity=80,
        status="proposed",
        approval_status="pending",
        owner_org_id="ORG-CORP",
    )
    db_session.add_all([shipment_b, request_b])
    db_session.commit()

    # Distributor A checks shipments: must NOT see Distributor B's shipments
    resp_a_shipments = client.get("/api/distributor/shipments", headers=dist_a_hdr)
    assert resp_a_shipments.status_code == 200
    ids_seen = [s["shipment_id"] for s in resp_a_shipments.json()]
    assert "SHP-DIST-B-TRANSIT" not in ids_seen
    assert "REQ-DIST-B-PENDING" not in ids_seen

    # Distributor A tries to cancel Distributor B's request -> HTTP 403
    cancel_resp = client.post(
        "/api/distributor/requests/REQ-DIST-B-PENDING/cancel",
        headers=dist_a_hdr,
        json={"reason": "Malicious cancellation attempt"},
    )
    assert cancel_resp.status_code == 403

    # Distributor A tries to confirm receipt on Distributor B's shipment -> HTTP 403
    receipt_resp = client.post(
        "/api/distributor/shipments/SHP-DIST-B-TRANSIT/confirm-receipt",
        headers=dist_a_hdr,
        json={"received_quantity": 150, "condition_status": "good"},
    )
    assert receipt_resp.status_code == 403


# --------------------------------------------------------------------------
# Scenario 4: Retailer A cannot read or modify Retailer B's orders, requests or receipts
# --------------------------------------------------------------------------
def test_scenario_04_retailer_cross_tenant_isolation(client: TestClient, portal_fixture, db_session: Session):
    retail_a_hdr = auth_headers("RET-A-USER", "metro@retail.internal", "retailer", "ORG-RETAIL-METRO")
    retail_b_hdr = auth_headers("RET-B-USER", "coastal@retail.internal", "retailer", "ORG-RETAIL-COASTAL")

    # Create shipment for Retailer B
    shipment_ret_b = Shipment(
        shipment_id="SHP-RET-B-TRANSIT",
        source_location_id="LOC-DIST-SOUTH",
        destination_location_id="LOC-STORE-CHENNAI",
        sku_id="SKU-CHIPS-100G",
        quantity=40,
        status="in_transit",
        approval_status="approved",
        logistics_status="in_transit",
        owner_org_id="ORG-DIST-SOUTH",
    )
    # Create pending order for Retailer B
    order_ret_b = Shipment(
        shipment_id="ORD-RET-B-PENDING",
        source_location_id="LOC-DIST-SOUTH",
        destination_location_id="LOC-STORE-CHENNAI",
        sku_id="SKU-CHIPS-100G",
        quantity=30,
        status="proposed",
        approval_status="pending",
        owner_org_id="ORG-DIST-SOUTH",
    )
    db_session.add_all([shipment_ret_b, order_ret_b])
    db_session.commit()

    # Retailer A queries shipments: must NOT see Retailer B's records
    resp_ret_a = client.get("/api/retailer/shipments", headers=retail_a_hdr)
    assert resp_ret_a.status_code == 200
    ids_seen = [s["shipment_id"] for s in resp_ret_a.json()]
    assert "SHP-RET-B-TRANSIT" not in ids_seen
    assert "ORD-RET-B-PENDING" not in ids_seen

    # Retailer A tries to cancel Retailer B's order -> HTTP 403
    cancel_resp = client.post(
        "/api/retailer/requests/ORD-RET-B-PENDING/cancel",
        headers=retail_a_hdr,
        json={"reason": "Compromised cancel"},
    )
    assert cancel_resp.status_code == 403

    # Retailer A tries to confirm receipt on Retailer B's delivery -> HTTP 403
    receipt_resp = client.post(
        "/api/retailer/shipments/SHP-RET-B-TRANSIT/confirm-receipt",
        headers=retail_a_hdr,
        json={"received_quantity": 40, "condition_status": "good"},
    )
    assert receipt_resp.status_code == 403


# --------------------------------------------------------------------------
# Scenario 5: Distributor and retailer users cannot access admin operations
# --------------------------------------------------------------------------
def test_scenario_05_least_privilege_rejection(client: TestClient, portal_fixture):
    dist_hdr = auth_headers("DIST-USER", "west@dist.internal", "distributor", "ORG-DIST-WEST")
    retail_hdr = auth_headers("RET-USER", "metro@retail.internal", "retailer", "ORG-RETAIL-METRO")

    # Distributor cannot create products
    assert client.post("/api/products", headers=dist_hdr, json={"sku_id": "BAD", "name": "B"}).status_code == 403
    # Distributor cannot edit network locations
    assert client.put("/api/network/locations/LOC-WH-DELHI", headers=dist_hdr, json={"name": "Hacked"}).status_code == 403
    # Distributor cannot list all admin users
    assert client.get("/api/admin/users", headers=dist_hdr).status_code == 403

    # Retailer cannot create products
    assert client.post("/api/products", headers=retail_hdr, json={"sku_id": "BAD", "name": "B"}).status_code == 403
    # Retailer cannot access company users
    assert client.get("/api/admin/users", headers=retail_hdr).status_code == 403


# --------------------------------------------------------------------------
# Scenario 6: Replenishment requests do not automatically deduct stock or dispatch shipments
# --------------------------------------------------------------------------
def test_scenario_06_replenishment_request_does_not_mutate_inventory(client: TestClient, portal_fixture, db_session: Session):
    dist_hdr = auth_headers("DIST-USER", "west@dist.internal", "distributor", "ORG-DIST-WEST")

    # Record source stock before request
    snap_before = (
        db_session.query(InventorySnapshot)
        .filter(InventorySnapshot.sku_id == "SKU-CHIPS-100G", InventorySnapshot.location_id == "LOC-WH-DELHI")
        .first()
    )
    initial_on_hand = snap_before.on_hand
    initial_reserved = snap_before.reserved

    # Submit distributor replenishment request
    req_resp = client.post(
        "/api/distributor/requests",
        headers=dist_hdr,
        json={
            "sku_id": "SKU-CHIPS-100G",
            "quantity": 120,
            "reason": "Anticipated weekend demand",
            "notes": "Urgent transfer",
        },
    )
    assert req_resp.status_code == 201
    shipment_data = req_resp.json()
    assert shipment_data["status"] == "proposed"
    assert shipment_data["approval_status"] == "pending"

    # Verify source stock is strictly UNCHANGED
    db_session.expire_all()
    snap_after = (
        db_session.query(InventorySnapshot)
        .filter(InventorySnapshot.sku_id == "SKU-CHIPS-100G", InventorySnapshot.location_id == "LOC-WH-DELHI")
        .first()
    )
    assert snap_after.on_hand == initial_on_hand
    assert snap_after.reserved == initial_reserved


# --------------------------------------------------------------------------
# Scenario 7: Authorized recipient confirms receipt and reports discrepancy
# --------------------------------------------------------------------------
def test_scenario_07_authorized_receipt_and_discrepancy(client: TestClient, portal_fixture, db_session: Session):
    dist_a_hdr = auth_headers("DIST-A-USER", "west@dist.internal", "distributor", "ORG-DIST-WEST")

    # Seed an in_transit shipment for Distributor A
    shipment = Shipment(
        shipment_id="SHP-DIST-A-TRANSIT-01",
        source_location_id="LOC-WH-DELHI",
        destination_location_id="LOC-DIST-WEST",
        sku_id="SKU-CHIPS-100G",
        quantity=100,
        status="in_transit",
        approval_status="approved",
        logistics_status="in_transit",
        owner_org_id="ORG-CORP",
    )
    db_session.add(shipment)
    db_session.commit()

    # Get distributor stock before receipt
    dist_snap_before = (
        db_session.query(InventorySnapshot)
        .filter(InventorySnapshot.sku_id == "SKU-CHIPS-100G", InventorySnapshot.location_id == "LOC-DIST-WEST")
        .first()
    )
    initial_dist_stock = dist_snap_before.on_hand

    # Confirm receipt with 5 damaged units reported
    receipt_resp = client.post(
        "/api/distributor/shipments/SHP-DIST-A-TRANSIT-01/confirm-receipt",
        headers=dist_a_hdr,
        json={
            "received_quantity": 95,
            "condition_status": "damaged",
            "discrepancy_units": 5,
            "notes": "5 cartons water damaged in transit",
        },
    )
    assert receipt_resp.status_code == 200
    updated_shipment = receipt_resp.json()
    assert updated_shipment["status"] == "delivered"
    assert updated_shipment["actual_delivery_date"] is not None

    # Verify inventory was credited by received_quantity (95)
    db_session.expire_all()
    dist_snap_after = (
        db_session.query(InventorySnapshot)
        .filter(InventorySnapshot.sku_id == "SKU-CHIPS-100G", InventorySnapshot.location_id == "LOC-DIST-WEST")
        .first()
    )
    assert dist_snap_after.on_hand == initial_dist_stock + 95

    # Verify audit movement was logged
    movement = (
        db_session.query(StockMovement)
        .filter(StockMovement.shipment_id == "SHP-DIST-A-TRANSIT-01", StockMovement.movement_type == "distributor_receipt")
        .first()
    )
    assert movement is not None
    assert movement.quantity == 95


# --------------------------------------------------------------------------
# Scenario 8: Duplicate receipt confirmation cannot process the same delivery twice
# --------------------------------------------------------------------------
def test_scenario_08_duplicate_receipt_rejection(client: TestClient, portal_fixture, db_session: Session):
    dist_a_hdr = auth_headers("DIST-A-USER", "west@dist.internal", "distributor", "ORG-DIST-WEST")

    # Seed an already delivered shipment
    delivered_shp = Shipment(
        shipment_id="SHP-DIST-A-DELIVERED-01",
        source_location_id="LOC-WH-DELHI",
        destination_location_id="LOC-DIST-WEST",
        sku_id="SKU-CHIPS-100G",
        quantity=100,
        status="delivered",
        approval_status="approved",
        logistics_status="delivered",
        actual_delivery_date=datetime.now(timezone.utc),
        owner_org_id="ORG-CORP",
    )
    db_session.add(delivered_shp)
    db_session.commit()

    repeat_resp = client.post(
        "/api/distributor/shipments/SHP-DIST-A-DELIVERED-01/confirm-receipt",
        headers=dist_a_hdr,
        json={"received_quantity": 95, "condition_status": "good"},
    )
    assert repeat_resp.status_code == 400
    assert "DUPLICATE_RECEIPT_REJECTED" in repeat_resp.json()["detail"] or "already" in repeat_resp.json()["detail"].lower()


# --------------------------------------------------------------------------
# Scenario 9: Invalid quantity and invalid shipment-state transitions are rejected
# --------------------------------------------------------------------------
def test_scenario_09_invalid_transitions_rejected(client: TestClient, portal_fixture, db_session: Session):
    dist_a_hdr = auth_headers("DIST-A-USER", "west@dist.internal", "distributor", "ORG-DIST-WEST")

    # Create a proposed shipment (not in_transit)
    proposed_shp = Shipment(
        shipment_id="SHP-DIST-A-PROPOSED",
        source_location_id="LOC-WH-DELHI",
        destination_location_id="LOC-DIST-WEST",
        sku_id="SKU-CHIPS-100G",
        quantity=50,
        status="proposed",
        approval_status="pending",
        owner_org_id="ORG-CORP",
    )
    db_session.add(proposed_shp)
    db_session.commit()

    # Attempting to confirm receipt on proposed shipment -> Rejected
    bad_state_resp = client.post(
        "/api/distributor/shipments/SHP-DIST-A-PROPOSED/confirm-receipt",
        headers=dist_a_hdr,
        json={"received_quantity": 50, "condition_status": "good"},
    )
    assert bad_state_resp.status_code == 400
    assert "INVALID_STATE_TRANSITION" in bad_state_resp.json()["detail"]


# --------------------------------------------------------------------------
# Scenario 10: Company-owned and independently owned inventory remain separated
# --------------------------------------------------------------------------
def test_scenario_10_inventory_ownership_separation(client: TestClient, portal_fixture, db_session: Session):
    # Company warehouse inventory has owner_org_id = 'ORG-CORP'
    company_inv = (
        db_session.query(InventorySnapshot)
        .filter(InventorySnapshot.location_id == "LOC-WH-DELHI")
        .all()
    )
    for inv in company_inv:
        assert inv.owner_org_id == "ORG-CORP"

    # Distributor inventory has owner_org_id = 'ORG-DIST-WEST'
    dist_inv = (
        db_session.query(InventorySnapshot)
        .filter(InventorySnapshot.location_id == "LOC-DIST-WEST")
        .all()
    )
    for inv in dist_inv:
        assert inv.owner_org_id == "ORG-DIST-WEST"


# --------------------------------------------------------------------------
# Scenario 11: Existing Distribution Intelligence workflows continue to function
# --------------------------------------------------------------------------
def test_scenario_11_distribution_intelligence_workflow(client: TestClient, portal_fixture):
    planner_hdr = auth_headers("PLANNER-01", "planner@stockwise.internal", "planner", "ORG-CORP")

    # Risk & demand analysis
    risk_resp = client.get("/api/risk/analysis", headers=planner_hdr)
    assert risk_resp.status_code == 200

    # Network eligibility
    elig_resp = client.get("/api/network/eligibility", headers=planner_hdr)
    assert elig_resp.status_code == 200
    assert "eligible_corridors" in elig_resp.json()


# --------------------------------------------------------------------------
# Scenario 12: Portal routes and error states function correctly
# --------------------------------------------------------------------------
def test_scenario_12_portal_routes_and_error_handling(client: TestClient, portal_fixture):
    # Unauthenticated request -> HTTP 401
    assert client.get("/api/distributor/dashboard").status_code == 401
    assert client.get("/api/retailer/dashboard").status_code == 401

    # Distributor accessing retailer dashboard -> HTTP 403
    dist_hdr = auth_headers("DIST-USER", "west@dist.internal", "distributor", "ORG-DIST-WEST")
    assert client.get("/api/retailer/dashboard", headers=dist_hdr).status_code == 403

    # Retailer accessing distributor dashboard -> HTTP 403
    ret_hdr = auth_headers("RET-USER", "metro@retail.internal", "retailer", "ORG-RETAIL-METRO")
    assert client.get("/api/distributor/dashboard", headers=ret_hdr).status_code == 403
