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

TEST_SECRET = "test-phase8-secret-must-be-at-least-32-chars-long!"


def generate_jwt(
    sub: str = "USER-DIST-01",
    email: str = None,
    role: str = "distributor",
    org_id: str = "ORG-DIST-A",
    secret: str = TEST_SECRET,
    app_metadata: dict = None,
    user_metadata: dict = None,
) -> str:
    now = datetime.now(timezone.utc)
    if email is None:
        email = f"{sub.lower()}@partner.internal"
    payload = {
        "sub": sub,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "app_metadata": app_metadata if app_metadata is not None else {"role": role, "org_id": org_id},
        "user_metadata": user_metadata or {},
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def dist_auth_headers(
    sub: str = "USER-DIST-01",
    role: str = "distributor",
    org_id: str = "ORG-DIST-A",
    user_metadata: dict = None,
) -> dict:
    token = generate_jwt(sub=sub, role=role, org_id=org_id, user_metadata=user_metadata)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def phase8_test_data(db_session: Session):
    """Seed test database with organizations, locations, products, and inventory."""
    old_env = settings.ENVIRONMENT
    old_secret = settings.SUPABASE_JWT_SECRET
    settings.SUPABASE_JWT_SECRET = TEST_SECRET
    settings.ENVIRONMENT = "production"

    # Organizations
    org_dist_a = Organization(org_id="ORG-DIST-A", name="Alpha Distributors West", org_type="distributor")
    org_dist_b = Organization(org_id="ORG-DIST-B", name="Beta Distributors South", org_type="distributor")
    org_corp = Organization(org_id="ORG-CORP", name="StockWise FMCG Corp", org_type="company")
    db_session.add_all([org_dist_a, org_dist_b, org_corp])

    # Locations
    loc_dist_a = Location(
        location_id="LOC-DIST-A",
        name="Alpha West Warehouse",
        location_type="distributor",
        region="West",
        owner_org_id="ORG-DIST-A",
        operator_org_id="ORG-DIST-A",
    )
    loc_dist_b = Location(
        location_id="LOC-DIST-B",
        name="Beta South Warehouse",
        location_type="distributor",
        region="South",
        owner_org_id="ORG-DIST-B",
        operator_org_id="ORG-DIST-B",
    )
    loc_hub = Location(
        location_id="LOC-HUB-CENTRAL",
        name="Central Hub",
        location_type="plant",
        region="West",
        owner_org_id="ORG-CORP",
        operator_org_id="ORG-CORP",
    )
    db_session.add_all([loc_dist_a, loc_dist_b, loc_hub])

    # Product
    prod1 = Product(sku_id="SKU-CHIPS-100G", name="Potato Chips 100g", category="Snacks", unit="cases")
    prod2 = Product(sku_id="SKU-BISCUITS-50G", name="Glucose Biscuits 50g", category="Biscuits", unit="cases")
    db_session.add_all([prod1, prod2])

    today = date.today()

    # Inventory Snapshots
    inv_a = InventorySnapshot(
        snapshot_id="SNAP-DIST-A-01",
        as_of_date=today,
        location_id="LOC-DIST-A",
        sku_id="SKU-CHIPS-100G",
        on_hand=500.0,
        reserved=50.0,
        blocked=0.0,
        owner_org_id="ORG-DIST-A",
        batch_number="BATCH-DISTA-01",
        expiry_date=today + timedelta(days=45),  # near expiry
    )
    inv_b = InventorySnapshot(
        snapshot_id="SNAP-DIST-B-01",
        as_of_date=today,
        location_id="LOC-DIST-B",
        sku_id="SKU-CHIPS-100G",
        on_hand=800.0,
        reserved=0.0,
        blocked=0.0,
        owner_org_id="ORG-DIST-B",
        batch_number="BATCH-DISTB-01",
        expiry_date=today + timedelta(days=180),
    )
    inv_corp = InventorySnapshot(
        snapshot_id="SNAP-CORP-01",
        as_of_date=today,
        location_id="LOC-HUB-CENTRAL",
        sku_id="SKU-BISCUITS-50G",
        on_hand=1500.0,
        reserved=100.0,
        blocked=0.0,
        owner_org_id="ORG-CORP",
        batch_number="BATCH-CORP-01",
        expiry_date=today + timedelta(days=200),
    )
    db_session.add_all([inv_a, inv_b, inv_corp])

    # Shipments
    ship_a = Shipment(
        shipment_id="SHIP-DIST-A-01",
        sku_id="SKU-CHIPS-100G",
        quantity=200.0,
        source_location_id="LOC-HUB-CENTRAL",
        destination_location_id="LOC-DIST-A",
        owner_org_id="ORG-DIST-A",
        status="in_transit",
        approval_status="approved",
    )
    ship_b = Shipment(
        shipment_id="SHIP-DIST-B-01",
        sku_id="SKU-CHIPS-100G",
        quantity=300.0,
        source_location_id="LOC-HUB-CENTRAL",
        destination_location_id="LOC-DIST-B",
        owner_org_id="ORG-DIST-B",
        status="in_transit",
        approval_status="approved",
    )
    db_session.add_all([ship_a, ship_b])

    db_session.commit()
    try:
        yield {
            "org_dist_a": org_dist_a,
            "org_dist_b": org_dist_b,
            "org_corp": org_corp,
        }
    finally:
        settings.ENVIRONMENT = old_env
        settings.SUPABASE_JWT_SECRET = old_secret


# =============================================================================
# 1. TEST: Authorized distributor can access their own inventory
# =============================================================================
def test_authorized_distributor_can_access_own_inventory(client: TestClient, phase8_test_data):
    """Distributor can fetch only inventory where owner_org_id matches user's org."""
    headers = dist_auth_headers(org_id="ORG-DIST-A")
    response = client.get("/api/distributor/inventory", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["snapshot_id"] == "SNAP-DIST-A-01"
    assert data[0]["owner_org_id"] == "ORG-DIST-A"
    assert data[0]["on_hand"] == 500.0
    assert data[0]["dispatchable_stock"] == 450.0


# =============================================================================
# 2. TEST: Distributor cannot access another organization's inventory
# =============================================================================
def test_distributor_cannot_access_another_organization_inventory(client: TestClient, phase8_test_data):
    """Distributor from ORG-DIST-A cannot see inventory of ORG-DIST-B or ORG-CORP."""
    headers = dist_auth_headers(org_id="ORG-DIST-A")
    response = client.get("/api/distributor/inventory", headers=headers)
    assert response.status_code == 200
    data = response.json()
    returned_snap_ids = [d["snapshot_id"] for d in data]
    assert "SNAP-DIST-B-01" not in returned_snap_ids
    assert "SNAP-CORP-01" not in returned_snap_ids


# =============================================================================
# 3. TEST: Distributor cannot read another organization's shipment
# =============================================================================
def test_distributor_cannot_read_another_organization_shipment(client: TestClient, phase8_test_data):
    """Distributor can only view shipments owned by or destined for their organization."""
    headers = dist_auth_headers(org_id="ORG-DIST-A")
    response = client.get("/api/distributor/shipments", headers=headers)
    assert response.status_code == 200
    data = response.json()
    returned_shipment_ids = [s["shipment_id"] for s in data]
    assert "SHIP-DIST-A-01" in returned_shipment_ids
    assert "SHIP-DIST-B-01" not in returned_shipment_ids


# =============================================================================
# 4. TEST: Invalid or non-positive request quantities are rejected
# =============================================================================
def test_invalid_or_non_positive_request_quantities_rejected(client: TestClient, phase8_test_data):
    """Quantities <= 0 must return HTTP 400 Bad Request."""
    headers = dist_auth_headers(org_id="ORG-DIST-A")

    # Zero quantity
    res_zero = client.post(
        "/api/distributor/requests",
        headers=headers,
        json={"sku_id": "SKU-CHIPS-100G", "quantity": 0, "reason": "Test"},
    )
    assert res_zero.status_code in (400, 422)

    # Negative quantity
    res_neg = client.post(
        "/api/distributor/requests",
        headers=headers,
        json={"sku_id": "SKU-CHIPS-100G", "quantity": -50, "reason": "Test"},
    )
    assert res_neg.status_code in (400, 422)


# =============================================================================
# 5. TEST: Request submission does not alter physical stock
# =============================================================================
def test_request_submission_does_not_alter_physical_stock(client: TestClient, db_session: Session, phase8_test_data):
    """
    Submitting a request creates a proposed shipment and does NOT mutate
    physical on_hand or reserved quantities.
    """
    headers = dist_auth_headers(org_id="ORG-DIST-A")
    payload = {
        "sku_id": "SKU-CHIPS-100G",
        "quantity": 100,
        "reason": "Prevent local stockout",
        "notes": "Urgent regional demand",
    }
    response = client.post("/api/distributor/requests", headers=headers, json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "proposed"
    assert created["approval_status"] == "pending"
    assert created["planning_run_id"].startswith("DIST-REQ-")

    # Verify inventory was NOT mutated
    inv = db_session.query(InventorySnapshot).filter(InventorySnapshot.snapshot_id == "SNAP-DIST-A-01").first()
    assert inv.on_hand == 500.0
    assert inv.reserved == 50.0
    assert inv.dispatchable_stock == 450.0


# =============================================================================
# 6. TEST: Distributor cannot self-assign an administrator role
# =============================================================================
def test_distributor_cannot_self_assign_admin_role(client: TestClient, phase8_test_data):
    """
    Attempting privilege escalation via user_metadata={"role": "admin"}
    is demoted to viewer and denied admin access.
    """
    # Unverified user claims admin in user_metadata
    token = generate_jwt(
        sub="USER-MALICIOUS-01",
        email="attacker@external.com",
        role="distributor",
        org_id="ORG-DIST-A",
        app_metadata={},  # no trusted role in app_metadata
        user_metadata={"role": "admin"},
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Attempting to call an admin-only endpoint like /api/imports/preview fails
    response = client.post(
        "/api/imports/preview",
        headers=headers,
        json={"dataset_type": "products", "rows": []},
    )
    assert response.status_code in (401, 403)


# =============================================================================
# 7. TEST: Requests require authenticated access
# =============================================================================
def test_requests_require_authenticated_access(client: TestClient, phase8_test_data):
    """Unauthenticated calls are rejected with HTTP 401."""
    res_dash = client.get("/api/distributor/dashboard")
    assert res_dash.status_code == 401

    res_post = client.post(
        "/api/distributor/requests",
        json={"sku_id": "SKU-CHIPS-100G", "quantity": 10},
    )
    assert res_post.status_code == 401


# =============================================================================
# 8. TEST: Distributor dashboard metrics and workflow compatibility
# =============================================================================
def test_distributor_dashboard_metrics_and_workflow_compatibility(client: TestClient, phase8_test_data):
    """
    Dashboard calculates accurate on-hand, dispatchable, near-expiry count,
    and returns recent shipments.
    """
    headers = dist_auth_headers(org_id="ORG-DIST-A")
    response = client.get("/api/distributor/dashboard", headers=headers)
    assert response.status_code == 200
    dash = response.json()

    assert dash["distributor_org_id"] == "ORG-DIST-A"
    assert dash["total_owned_skus"] == 1
    assert dash["total_on_hand_units"] == 500.0
    assert dash["total_dispatchable_units"] == 450.0
    assert dash["near_expiry_batches_count"] == 1
    assert dash["in_transit_shipments_count"] == 1
    assert len(dash["recent_shipments"]) >= 1
    assert dash["recent_shipments"][0]["shipment_id"] == "SHIP-DIST-A-01"
