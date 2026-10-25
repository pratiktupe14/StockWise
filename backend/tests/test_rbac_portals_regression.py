"""
Regression Test Suite for Role-Based Access Control (RBAC) & Portal Authorization.

Validates the full authorization matrix across all five workspaces:
1. Planner can access authorized planning endpoints.
2. Planner cannot access distributor-only endpoints without explicit permission.
3. Planner cannot access retailer-only endpoints without explicit permission.
4. Distributor can access its own portal and authorized records.
5. Distributor cannot access another organization's records (cross-tenant isolation).
6. Retailer can access its own portal and authorized records.
7. Retailer cannot access distributor-only or competitor-store records.
8. Unauthenticated users are rejected with HTTP 401.
9. Privilege escalation via client user_metadata is demoted to viewer.
10. Demo personas preserve isolated identity and organizational contexts.
11. Admin can access company-wide administrative functions and both portals.
"""

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
    SalesHistory,
)

TEST_SECRET = "test-jwt-secret-for-rbac-regression-tests-must-be-32-chars!"


def make_jwt(
    sub: str = "USER-TEST",
    email: str = "test@partner.internal",
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


def rbac_auth_headers(
    sub: str,
    email: str,
    role: str,
    org_id: str,
    user_metadata: dict = None,
) -> dict:
    token = make_jwt(sub=sub, email=email, role=role, org_id=org_id, user_metadata=user_metadata)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def rbac_fixture(db_session: Session):
    """Seeds multi-tenant FMCG organizations, locations, inventory, and sales."""
    old_env = settings.ENVIRONMENT
    old_secret = settings.SUPABASE_JWT_SECRET
    settings.SUPABASE_JWT_SECRET = TEST_SECRET
    settings.ENVIRONMENT = "production"

    # 1. Organizations
    org_corp = Organization(org_id="ORG-FMCG-CORP", name="Britannia FMCG Corp", org_type="fmcg_company")
    org_dist_a = Organization(org_id="ORG-DIST-WEST", name="Apex West Distributors", org_type="distributor")
    org_dist_b = Organization(org_id="ORG-DIST-SOUTH", name="South Apex Distributors", org_type="distributor")
    org_ret_a = Organization(org_id="ORG-RETAIL-METRO", name="Metro Mart Retail #101", org_type="retailer")
    org_ret_b = Organization(org_id="ORG-RETAIL-QUICK", name="QuickMart Competitor #202", org_type="retailer")
    org_3pl = Organization(org_id="ORG-LOGISTICS-3PL", name="BlueDart Freight Consortium", org_type="logistics_provider")
    db_session.add_all([org_corp, org_dist_a, org_dist_b, org_ret_a, org_ret_b, org_3pl])

    # 2. Locations
    loc_hub = Location(
        location_id="LOC-WH-CENTRAL",
        name="Central DC Bhiwandi",
        location_type="company_warehouse",
        region="West",
        owner_org_id="ORG-FMCG-CORP",
    )
    loc_dist_a = Location(
        location_id="LOC-DIST-WEST",
        name="Apex West Hub",
        location_type="distributor",
        region="West",
        owner_org_id="ORG-DIST-WEST",
        operator_org_id="ORG-DIST-WEST",
    )
    loc_dist_b = Location(
        location_id="LOC-DIST-SOUTH",
        name="South Apex Hub",
        location_type="distributor",
        region="South",
        owner_org_id="ORG-DIST-SOUTH",
        operator_org_id="ORG-DIST-SOUTH",
    )
    loc_store_a = Location(
        location_id="LOC-STORE-101",
        name="Metro Mart Store #101",
        location_type="retailer",
        region="West",
        owner_org_id="ORG-RETAIL-METRO",
        operator_org_id="ORG-RETAIL-METRO",
    )
    loc_store_b = Location(
        location_id="LOC-STORE-202",
        name="QuickMart Store #202",
        location_type="retailer",
        region="West",
        owner_org_id="ORG-RETAIL-QUICK",
        operator_org_id="ORG-RETAIL-QUICK",
    )
    db_session.add_all([loc_hub, loc_dist_a, loc_dist_b, loc_store_a, loc_store_b])

    # 3. Product Catalog
    prod = Product(sku_id="SKU-GOODDAY-100", name="Good Day Butter Cookies 120g", category="Biscuits", unit="cases")
    db_session.add(prod)

    today = date.today()

    # 4. Inventory Snapshots
    inv_dist_a = InventorySnapshot(
        snapshot_id="SNAP-DIST-A",
        sku_id="SKU-GOODDAY-100",
        location_id="LOC-DIST-WEST",
        owner_org_id="ORG-DIST-WEST",
        on_hand=400.0,
        reserved=0.0,
        blocked=0.0,
        as_of_date=today,
    )
    inv_dist_b = InventorySnapshot(
        snapshot_id="SNAP-DIST-B",
        sku_id="SKU-GOODDAY-100",
        location_id="LOC-DIST-SOUTH",
        owner_org_id="ORG-DIST-SOUTH",
        on_hand=250.0,
        reserved=0.0,
        blocked=0.0,
        as_of_date=today,
    )
    inv_ret_a = InventorySnapshot(
        snapshot_id="SNAP-RET-A",
        sku_id="SKU-GOODDAY-100",
        location_id="LOC-STORE-101",
        owner_org_id="ORG-RETAIL-METRO",
        on_hand=35.0,
        reserved=0.0,
        blocked=0.0,
        as_of_date=today,
    )
    inv_ret_b = InventorySnapshot(
        snapshot_id="SNAP-RET-B",
        sku_id="SKU-GOODDAY-100",
        location_id="LOC-STORE-202",
        owner_org_id="ORG-RETAIL-QUICK",
        on_hand=80.0,
        reserved=0.0,
        blocked=0.0,
        as_of_date=today,
    )
    db_session.add_all([inv_dist_a, inv_dist_b, inv_ret_a, inv_ret_b])

    # 5. Sales History for Forecast / Planning
    sales = [
        SalesHistory(
            sku_id="SKU-GOODDAY-100",
            destination_id="LOC-STORE-101",
            sales_date=today - timedelta(days=i),
            quantity=25.0,
        )
        for i in range(1, 15)
    ]
    db_session.add_all(sales)
    db_session.commit()

    yield

    settings.ENVIRONMENT = old_env
    settings.SUPABASE_JWT_SECRET = old_secret


# =============================================================================
# 1. PLANNER ACCESS: Authorized planning endpoints
# =============================================================================

def test_planner_can_access_authorized_planning_endpoints(client: TestClient, rbac_fixture):
    """Planner can access demand forecasting and risk analysis."""
    headers = rbac_auth_headers(
        sub="USER-PLANNER-01",
        email="planner@stockwise.internal",
        role="planner",
        org_id="ORG-FMCG-CORP",
    )

    # 1. Demand Forecast endpoint
    res_fc = client.get("/api/forecast?horizon_days=7", headers=headers)
    assert res_fc.status_code == 200, res_fc.text
    data = res_fc.json()
    assert "forecasts" in data

    # 2. Inventory Risk Analysis endpoint
    res_risk = client.get("/api/risk/analysis?horizon_days=7", headers=headers)
    assert res_risk.status_code == 200, res_risk.text
    risk_data = res_risk.json()
    assert "items" in risk_data


# =============================================================================
# 2. PLANNER ACCESS DENIED: Cannot access distributor-only endpoints
# =============================================================================

def test_planner_cannot_access_distributor_only_endpoints(client: TestClient, rbac_fixture):
    """Planner accessing distributor-only endpoints is rejected with HTTP 403."""
    headers = rbac_auth_headers(
        sub="USER-PLANNER-01",
        email="planner@stockwise.internal",
        role="planner",
        org_id="ORG-FMCG-CORP",
    )

    # Dashboard
    res_dash = client.get("/api/distributor/dashboard", headers=headers)
    assert res_dash.status_code == 403
    assert "Required role: admin, distributor (current: 'planner')" in res_dash.json()["detail"]

    # Inventory
    res_inv = client.get("/api/distributor/inventory", headers=headers)
    assert res_inv.status_code == 403
    assert "Required role: admin, distributor (current: 'planner')" in res_inv.json()["detail"]

    # Requests
    res_req = client.get("/api/distributor/requests", headers=headers)
    assert res_req.status_code == 403

    # Submit request
    res_post = client.post(
        "/api/distributor/requests",
        headers=headers,
        json={"sku_id": "SKU-GOODDAY-100", "quantity": 50},
    )
    assert res_post.status_code == 403


# =============================================================================
# 3. PLANNER ACCESS DENIED: Cannot access retailer-only endpoints
# =============================================================================

def test_planner_cannot_access_retailer_only_endpoints(client: TestClient, rbac_fixture):
    """Planner accessing retailer-only endpoints is rejected with HTTP 403."""
    headers = rbac_auth_headers(
        sub="USER-PLANNER-01",
        email="planner@stockwise.internal",
        role="planner",
        org_id="ORG-FMCG-CORP",
    )

    # Dashboard
    res_dash = client.get("/api/retailer/dashboard", headers=headers)
    assert res_dash.status_code == 403
    assert "Required role: admin, retailer (current: 'planner')" in res_dash.json()["detail"]

    # Inventory
    res_inv = client.get("/api/retailer/inventory", headers=headers)
    assert res_inv.status_code == 403

    # Requests
    res_req = client.get("/api/retailer/requests", headers=headers)
    assert res_req.status_code == 403

    # Submit request
    res_post = client.post(
        "/api/retailer/requests",
        headers=headers,
        json={"sku_id": "SKU-GOODDAY-100", "quantity": 20},
    )
    assert res_post.status_code == 403


# =============================================================================
# 4. DISTRIBUTOR ACCESS: Authorized distributor can access own portal & catalog
# =============================================================================

def test_distributor_can_access_own_portal_and_authorized_records(client: TestClient, rbac_fixture):
    """Distributor accesses own dashboard, inventory, requests, shipments, and products."""
    headers = rbac_auth_headers(
        sub="USER-DISTRIBUTOR-01",
        email="distributor@stockwise.internal",
        role="distributor",
        org_id="ORG-DIST-WEST",
    )

    # Dashboard
    res_dash = client.get("/api/distributor/dashboard", headers=headers)
    assert res_dash.status_code == 200, res_dash.text
    dash = res_dash.json()
    assert dash["distributor_org_id"] == "ORG-DIST-WEST"
    assert dash["total_on_hand_units"] == 400.0

    # Own Inventory
    res_inv = client.get("/api/distributor/inventory", headers=headers)
    assert res_inv.status_code == 200
    inv = res_inv.json()
    assert len(inv) == 1
    assert inv[0]["owner_org_id"] == "ORG-DIST-WEST"

    # Requests
    res_req = client.get("/api/distributor/requests", headers=headers)
    assert res_req.status_code == 200

    # Shipments
    res_ship = client.get("/api/distributor/shipments", headers=headers)
    assert res_ship.status_code == 200

    # Cannot access internal company administration endpoints like /api/organizations
    res_orgs = client.get("/api/organizations", headers=headers)
    assert res_orgs.status_code == 403


# =============================================================================
# 5. DISTRIBUTOR CROSS-TENANT ISOLATION: Cannot access another distributor's records
# =============================================================================

def test_distributor_cannot_access_another_organization_records(client: TestClient, rbac_fixture):
    """Distributor cannot specify another org_id or access competitor inventory."""
    headers = rbac_auth_headers(
        sub="USER-DISTRIBUTOR-01",
        email="distributor@stockwise.internal",
        role="distributor",
        org_id="ORG-DIST-WEST",
    )

    # Attempt to inspect South Apex inventory by setting distributor_org_id query param
    res_inv = client.get("/api/distributor/inventory?distributor_org_id=ORG-DIST-SOUTH", headers=headers)
    assert res_inv.status_code == 403
    assert "Forbidden: You are not authorized to access organization 'ORG-DIST-SOUTH'" in res_inv.json()["detail"]

    # Attempt to inspect South Apex dashboard
    res_dash = client.get("/api/distributor/dashboard?distributor_org_id=ORG-DIST-SOUTH", headers=headers)
    assert res_dash.status_code == 403

    # Attempt to access Retailer Portal
    res_ret = client.get("/api/retailer/dashboard", headers=headers)
    assert res_ret.status_code == 403
    assert "Required role: admin, retailer (current: 'distributor')" in res_ret.json()["detail"]


# =============================================================================
# 6. RETAILER ACCESS: Authorized retailer can access own store portal & catalog
# =============================================================================

def test_retailer_can_access_own_portal_and_authorized_records(client: TestClient, rbac_fixture):
    """Retailer accesses own dashboard, inventory, requests, shipments, and products."""
    headers = rbac_auth_headers(
        sub="USER-RETAILER-01",
        email="retailer@stockwise.internal",
        role="retailer",
        org_id="ORG-RETAIL-METRO",
    )

    # Dashboard
    res_dash = client.get("/api/retailer/dashboard", headers=headers)
    assert res_dash.status_code == 200, res_dash.text
    dash = res_dash.json()
    assert dash["retailer_org_id"] == "ORG-RETAIL-METRO"
    assert dash["total_on_hand_units"] == 35.0

    # Own Inventory
    res_inv = client.get("/api/retailer/inventory", headers=headers)
    assert res_inv.status_code == 200
    inv = res_inv.json()
    assert len(inv) == 1
    assert inv[0]["owner_org_id"] == "ORG-RETAIL-METRO"

    # Requests
    res_req = client.get("/api/retailer/requests", headers=headers)
    assert res_req.status_code == 200

    # Shipments
    res_ship = client.get("/api/retailer/shipments", headers=headers)
    assert res_ship.status_code == 200

    # Cannot access internal company administration endpoints like /api/organizations
    res_orgs = client.get("/api/organizations", headers=headers)
    assert res_orgs.status_code == 403


# =============================================================================
# 7. RETAILER CROSS-TENANT ISOLATION: Cannot access competitor store or distributor
# =============================================================================

def test_retailer_cannot_access_distributor_or_competitor_records(client: TestClient, rbac_fixture):
    """Retailer cannot access distributor records or competitor retailer store."""
    headers = rbac_auth_headers(
        sub="USER-RETAILER-01",
        email="retailer@stockwise.internal",
        role="retailer",
        org_id="ORG-RETAIL-METRO",
    )

    # Attempt to access competitor store #202
    res_comp = client.get("/api/retailer/dashboard?retailer_org_id=ORG-RETAIL-QUICK", headers=headers)
    assert res_comp.status_code == 403
    assert "Forbidden: You are not authorized to access organization 'ORG-RETAIL-QUICK'" in res_comp.json()["detail"]

    # Attempt to access distributor inventory
    res_dist = client.get("/api/distributor/dashboard", headers=headers)
    assert res_dist.status_code == 403
    assert "Required role: admin, distributor (current: 'retailer')" in res_dist.json()["detail"]

    # Attempt to access planner forecast
    res_plan = client.get("/api/forecast", headers=headers)
    assert res_plan.status_code == 403


# =============================================================================
# 8. UNAUTHENTICATED USERS: Rejected with HTTP 401
# =============================================================================

def test_unauthenticated_requests_are_rejected(client: TestClient, rbac_fixture):
    """Unauthenticated calls in production environment return HTTP 401."""
    assert client.get("/api/forecast").status_code == 401
    assert client.get("/api/distributor/dashboard").status_code == 401
    assert client.get("/api/retailer/dashboard").status_code == 401
    assert client.get("/api/products").status_code == 401
    assert client.get("/api/organizations").status_code == 401


# =============================================================================
# 9. PRIVILEGE ESCALATION PREVENTION: user_metadata cannot elevate to privileged roles
# =============================================================================

def test_user_metadata_role_elevation_is_demoted_and_rejected(client: TestClient, rbac_fixture):
    """Client-controlled user_metadata attempting privileged role assignment is demoted to viewer."""
    for malicious_role in ["admin", "planner", "distributor", "retailer"]:
        token = make_jwt(
            sub="USER-ATTACKER-01",
            email="attacker@external-evil.com",
            app_metadata={},  # No trusted app_metadata
            user_metadata={"role": malicious_role, "org_id": "ORG-FMCG-CORP"},
        )
        headers = {"Authorization": f"Bearer {token}"}

        # Attempting to access admin-only endpoint fails
        res_admin = client.post("/api/organizations", headers=headers, json={"org_id": "ORG-NEW", "name": "Evil", "org_type": "distributor"})
        assert res_admin.status_code in (401, 403), f"Failed for role {malicious_role}"

        # Attempting distributor portal fails
        res_dist = client.get("/api/distributor/dashboard", headers=headers)
        assert res_dist.status_code == 403, f"Failed for role {malicious_role}"
        assert "Required role: admin, distributor (current: 'viewer')" in res_dist.json()["detail"]


# =============================================================================
# 10. DEMO PERSONAS: Verified roles and organizations in demo mode
# =============================================================================

def test_demo_personas_have_correct_trusted_roles_and_tenants(client: TestClient, db_session, monkeypatch):
    """Demo authentication headers correctly resolve dedicated personas."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "ALLOW_DEMO_AUTH", True)

    # 1. Planner persona
    h_planner = {"Authorization": "Bearer demo-planner-token"}
    res_plan = client.get("/api/forecast", headers=h_planner)
    assert res_plan.status_code == 200

    # 2. Distributor persona
    h_dist = {"Authorization": "Bearer demo-distributor-token"}
    res_dist = client.get("/api/distributor/dashboard", headers=h_dist)
    assert res_dist.status_code == 200
    assert res_dist.json()["distributor_org_id"] == "ORG-DIST-WEST"

    # 3. Retailer persona
    h_ret = {"Authorization": "Bearer demo-retailer-token"}
    res_ret = client.get("/api/retailer/dashboard", headers=h_ret)
    assert res_ret.status_code == 200
    assert res_ret.json()["retailer_org_id"] == "ORG-RETAIL-METRO"


# =============================================================================
# 11. ADMIN ACCESS: Admin has company-wide access across both portals
# =============================================================================

def test_admin_can_access_both_distributor_and_retailer_portals(client: TestClient, rbac_fixture):
    """Company admin can inspect both distributor and retailer portals and cross-tenant data."""
    headers = rbac_auth_headers(
        sub="USER-ADMIN-01",
        email="admin@stockwise.internal",
        role="admin",
        org_id="ORG-FMCG-CORP",
    )

    # Admin visits Distributor Portal
    res_dist = client.get("/api/distributor/dashboard", headers=headers)
    assert res_dist.status_code == 200
    assert res_dist.json()["distributor_org_id"] == "ORG-DIST-WEST"

    # Admin visits specific distributor
    res_dist_south = client.get("/api/distributor/dashboard?distributor_org_id=ORG-DIST-SOUTH", headers=headers)
    assert res_dist_south.status_code == 200
    assert res_dist_south.json()["distributor_org_id"] == "ORG-DIST-SOUTH"

    # Admin visits Retailer Portal
    res_ret = client.get("/api/retailer/dashboard", headers=headers)
    assert res_ret.status_code == 200
    assert res_ret.json()["retailer_org_id"] == "ORG-RETAIL-METRO"

    # Admin visits specific retailer
    res_ret_quick = client.get("/api/retailer/dashboard?retailer_org_id=ORG-RETAIL-QUICK", headers=headers)
    assert res_ret_quick.status_code == 200
    assert res_ret_quick.json()["retailer_org_id"] == "ORG-RETAIL-QUICK"
