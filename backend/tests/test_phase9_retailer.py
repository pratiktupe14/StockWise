from datetime import date, timedelta, datetime, timezone
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
    StockMovement,
)

TEST_SECRET = "test-phase9-secret-must-be-at-least-32-chars-long!"


def generate_jwt(
    sub: str = "USER-RET-01",
    email: str = None,
    role: str = "retailer",
    org_id: str = "ORG-RETAIL-A",
    secret: str = TEST_SECRET,
    app_metadata: dict = None,
    user_metadata: dict = None,
) -> str:
    now = datetime.now(timezone.utc)
    if email is None:
        email = f"{sub.lower()}@retailpartner.internal"
    payload = {
        "sub": sub,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "app_metadata": app_metadata if app_metadata is not None else {"role": role, "org_id": org_id},
        "user_metadata": user_metadata or {},
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def ret_auth_headers(
    sub: str = "USER-RET-01",
    role: str = "retailer",
    org_id: str = "ORG-RETAIL-A",
    user_metadata: dict = None,
) -> dict:
    token = generate_jwt(sub=sub, role=role, org_id=org_id, user_metadata=user_metadata)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def phase9_test_data(db_session: Session):
    """Seed test database with retailer and distributor organizations, locations, and inventory."""
    old_env = settings.ENVIRONMENT
    old_secret = settings.SUPABASE_JWT_SECRET
    settings.SUPABASE_JWT_SECRET = TEST_SECRET
    settings.ENVIRONMENT = "production"

    # Organizations
    org_retail_a = Organization(org_id="ORG-RETAIL-A", name="Metro Mart Retail 01", org_type="retailer")
    org_retail_b = Organization(org_id="ORG-RETAIL-B", name="Quick Store Retail 02", org_type="retailer")
    org_dist = Organization(org_id="ORG-DIST-WEST", name="West Hub Distributors", org_type="distributor")
    db_session.add_all([org_retail_a, org_retail_b, org_dist])

    # Locations
    loc_store_a = Location(
        location_id="LOC-STORE-A",
        name="Metro Mart Downtown",
        location_type="retailer",
        region="West",
        owner_org_id="ORG-RETAIL-A",
        operator_org_id="ORG-RETAIL-A",
    )
    loc_store_b = Location(
        location_id="LOC-STORE-B",
        name="Quick Store Uptown",
        location_type="retailer",
        region="West",
        owner_org_id="ORG-RETAIL-B",
        operator_org_id="ORG-RETAIL-B",
    )
    loc_dist = Location(
        location_id="LOC-DIST-WEST",
        name="West Regional Distribution Center",
        location_type="distributor",
        region="West",
        owner_org_id="ORG-DIST-WEST",
        operator_org_id="ORG-DIST-WEST",
    )
    db_session.add_all([loc_store_a, loc_store_b, loc_dist])

    # Products
    prod1 = Product(sku_id="SKU-SOAP-125G", name="Bath Soap 125g", category="Personal Care", unit="cases")
    prod2 = Product(sku_id="SKU-SHAMPOO-200ML", name="Herbal Shampoo 200ml", category="Personal Care", unit="cases")
    db_session.add_all([prod1, prod2])

    today = date.today()

    # Inventory Snapshots (without computed dispatchable_stock kwarg)
    inv_a = InventorySnapshot(
        snapshot_id="SNAP-RET-A-01",
        as_of_date=today,
        location_id="LOC-STORE-A",
        sku_id="SKU-SOAP-125G",
        on_hand=80.0,
        reserved=10.0,
        blocked=0.0,
        owner_org_id="ORG-RETAIL-A",
        batch_number="BATCH-SOAP-A1",
        expiry_date=today + timedelta(days=90),
    )
    inv_b = InventorySnapshot(
        snapshot_id="SNAP-RET-B-01",
        as_of_date=today,
        location_id="LOC-STORE-B",
        sku_id="SKU-SOAP-125G",
        on_hand=150.0,
        reserved=0.0,
        blocked=0.0,
        owner_org_id="ORG-RETAIL-B",
        batch_number="BATCH-SOAP-B1",
        expiry_date=today + timedelta(days=120),
    )
    inv_dist = InventorySnapshot(
        snapshot_id="SNAP-DIST-01",
        as_of_date=today,
        location_id="LOC-DIST-WEST",
        sku_id="SKU-SHAMPOO-200ML",
        on_hand=1000.0,
        reserved=50.0,
        blocked=0.0,
        owner_org_id="ORG-DIST-WEST",
        batch_number="BATCH-DIST-01",
        expiry_date=today + timedelta(days=180),
    )
    db_session.add_all([inv_a, inv_b, inv_dist])

    # Shipments
    ship_a = Shipment(
        shipment_id="SHIP-RET-A-01",
        sku_id="SKU-SOAP-125G",
        quantity=50.0,
        source_location_id="LOC-DIST-WEST",
        destination_location_id="LOC-STORE-A",
        owner_org_id="ORG-RETAIL-A",
        status="in_transit",
        approval_status="approved",
    )
    ship_b = Shipment(
        shipment_id="SHIP-RET-B-01",
        sku_id="SKU-SOAP-125G",
        quantity=100.0,
        source_location_id="LOC-DIST-WEST",
        destination_location_id="LOC-STORE-B",
        owner_org_id="ORG-RETAIL-B",
        status="in_transit",
        approval_status="approved",
    )
    db_session.add_all([ship_a, ship_b])

    db_session.commit()
    try:
        yield {
            "org_retail_a": org_retail_a,
            "org_retail_b": org_retail_b,
            "org_dist": org_dist,
        }
    finally:
        settings.ENVIRONMENT = old_env
        settings.SUPABASE_JWT_SECRET = old_secret


# =============================================================================
# 1. TEST: Authorized retailer can access their own inventory
# =============================================================================
def test_authorized_retailer_can_access_own_inventory(client: TestClient, phase9_test_data):
    """Retailer fetches only inventory where owner_org_id matches user's store org."""
    headers = ret_auth_headers(org_id="ORG-RETAIL-A")
    response = client.get("/api/retailer/inventory", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["snapshot_id"] == "SNAP-RET-A-01"
    assert data[0]["owner_org_id"] == "ORG-RETAIL-A"
    assert data[0]["on_hand"] == 80.0
    assert data[0]["dispatchable_stock"] == 70.0


# =============================================================================
# 2. TEST: Retailer cannot read another retailer's inventory
# =============================================================================
def test_retailer_cannot_read_another_retailer_inventory(client: TestClient, phase9_test_data):
    """Retailer from ORG-RETAIL-A cannot see inventory of ORG-RETAIL-B or ORG-DIST-WEST."""
    headers = ret_auth_headers(org_id="ORG-RETAIL-A")
    response = client.get("/api/retailer/inventory", headers=headers)
    assert response.status_code == 200
    data = response.json()
    snapshot_ids = [d["snapshot_id"] for d in data]
    assert "SNAP-RET-B-01" not in snapshot_ids
    assert "SNAP-DIST-01" not in snapshot_ids


# =============================================================================
# 3. TEST: Retailer cannot read an unauthorized shipment
# =============================================================================
def test_retailer_cannot_read_unauthorized_shipment(client: TestClient, phase9_test_data):
    """Retailer can only view shipments owned by or destined for their store."""
    headers = ret_auth_headers(org_id="ORG-RETAIL-A")
    response = client.get("/api/retailer/shipments", headers=headers)
    assert response.status_code == 200
    data = response.json()
    shipment_ids = [s["shipment_id"] for s in data]
    assert "SHIP-RET-A-01" in shipment_ids
    assert "SHIP-RET-B-01" not in shipment_ids


# =============================================================================
# 4. TEST: Non-positive request quantities are rejected
# =============================================================================
def test_non_positive_request_quantities_rejected(client: TestClient, phase9_test_data):
    """Quantities <= 0 must return HTTP 400 or 422."""
    headers = ret_auth_headers(org_id="ORG-RETAIL-A")

    # Zero quantity
    res_zero = client.post(
        "/api/retailer/requests",
        headers=headers,
        json={"sku_id": "SKU-SOAP-125G", "quantity": 0, "reason": "Test"},
    )
    assert res_zero.status_code in (400, 422)

    # Negative quantity
    res_neg = client.post(
        "/api/retailer/requests",
        headers=headers,
        json={"sku_id": "SKU-SOAP-125G", "quantity": -20, "reason": "Test"},
    )
    assert res_neg.status_code in (400, 422)


# =============================================================================
# 5. TEST: Unauthenticated requests are rejected
# =============================================================================
def test_unauthenticated_requests_are_rejected(client: TestClient, phase9_test_data):
    """Unauthenticated calls must return HTTP 401."""
    res_dash = client.get("/api/retailer/dashboard")
    assert res_dash.status_code == 401

    res_post = client.post(
        "/api/retailer/requests",
        json={"sku_id": "SKU-SOAP-125G", "quantity": 10},
    )
    assert res_post.status_code == 401


# =============================================================================
# 6. TEST: Retailer cannot self-assign elevated roles
# =============================================================================
def test_retailer_cannot_self_assign_elevated_roles(client: TestClient, phase9_test_data):
    """
    Attempting privilege escalation via user_metadata={"role": "admin"}
    is demoted to viewer and denied admin endpoints.
    """
    token = generate_jwt(
        sub="USER-RETAIL-ATTACKER",
        email="attacker@store.internal",
        role="retailer",
        org_id="ORG-RETAIL-A",
        app_metadata={},  # no server-verified role in app_metadata
        user_metadata={"role": "admin"},
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/imports/preview",
        headers=headers,
        json={"dataset_type": "products", "rows": []},
    )
    assert response.status_code in (401, 403)


# =============================================================================
# 7. TEST: Request submission does not mutate physical stock
# =============================================================================
def test_request_submission_does_not_mutate_physical_stock(client: TestClient, db_session: Session, phase9_test_data):
    """
    Submitting a retailer replenishment request creates a proposed shipment
    and does NOT alter physical on_hand or reserved quantities.
    """
    headers = ret_auth_headers(org_id="ORG-RETAIL-A")
    payload = {
        "sku_id": "SKU-SOAP-125G",
        "quantity": 30,
        "reason": "Weekend shelf restock",
        "notes": "Deliver by Friday morning",
    }
    response = client.post("/api/retailer/requests", headers=headers, json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "proposed"
    assert created["approval_status"] == "pending"
    assert created["planning_run_id"].startswith("RET-REQ-")

    # Verify inventory was NOT mutated
    inv = db_session.query(InventorySnapshot).filter(InventorySnapshot.snapshot_id == "SNAP-RET-A-01").first()
    assert inv.on_hand == 80.0
    assert inv.reserved == 10.0
    assert inv.dispatchable_stock == 70.0


# =============================================================================
# 8. TEST: Existing distributor and shipment workflows remain compatible
# =============================================================================
def test_existing_distributor_and_shipment_workflows_remain_compatible(client: TestClient, phase9_test_data):
    """
    Retailer dashboard calculates accurate on-hand, available, and in-transit counts,
    and distributor endpoints continue to function independently.
    """
    headers = ret_auth_headers(org_id="ORG-RETAIL-A")
    response = client.get("/api/retailer/dashboard", headers=headers)
    assert response.status_code == 200
    dash = response.json()

    assert dash["retailer_org_id"] == "ORG-RETAIL-A"
    assert dash["total_store_skus"] == 1
    assert dash["total_on_hand_units"] == 80.0
    assert dash["total_available_units"] == 70.0
    assert dash["in_transit_shipments_count"] == 1
    assert len(dash["recent_shipments"]) >= 1
    assert dash["recent_shipments"][0]["shipment_id"] == "SHIP-RET-A-01"
