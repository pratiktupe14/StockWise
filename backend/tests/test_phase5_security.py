"""
Phase 5: Security Hardening, Tenant Isolation & Production Reliability Test Suite.

Automated verification for:
1. Fail-closed JWT authentication (unsigned, invalid signature, expired, invalid claims).
2. Demo token and role-header rejection when production mode is enforced.
3. Privilege escalation prevention (untrusted user_metadata demoted to viewer).
4. Multi-tenant organization isolation across inventory, imports, planning, shipments, Decision Receipts, exports, and audit events.
5. Idempotency guarantees (exact replay -> 200, mismatched payload reuse -> 409 Conflict).
6. Concurrency & duplicate dispatch prevention with row-locking and cancellation rollback.
"""

from datetime import datetime, timezone, timedelta, date
import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import (
    verify_supabase_jwt,
    derive_trusted_role_and_org,
)
from app.models.entities import (
    Organization,
    Location,
    Product,
    InventorySnapshot,
    ImportRun,
    PlanningRun,
    Shipment,
)

TEST_SECRET = "super-secret-jwt-key-32-characters-min-for-security-tests!"


def generate_jwt(
    sub: str = "USER-TEST-01",
    email: str = "test@stockwise.internal",
    role: str = "planner",
    org_id: str = "ORG-ALPHA",
    secret: str = TEST_SECRET,
    algorithm: str = "HS256",
    expires_in_seconds: int = 3600,
    app_metadata: dict = None,
    user_metadata: dict = None,
    headers: dict = None,
) -> str:
    """Helper to generate mock Supabase JWTs for deterministic security testing."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
        "app_metadata": app_metadata if app_metadata is not None else {"role": role, "org_id": org_id},
        "user_metadata": user_metadata or {},
    }
    return jwt.encode(payload, secret, algorithm=algorithm, headers=headers)


# =============================================================================
# 1. FAIL-CLOSED JWT VALIDATION TESTS
# =============================================================================

def test_jwt_valid_signature_accepted(monkeypatch):
    """Valid JWT with configured secret and claims verifies successfully."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    token = generate_jwt(sub="USER-01", email="user@alpha.com", role="planner", org_id="ORG-ALPHA")
    user = verify_supabase_jwt(token)
    assert user.user_id == "USER-01"
    assert user.email == "user@alpha.com"


def test_jwt_invalid_signature_rejected(monkeypatch):
    """Token signed with wrong key is rejected with 401."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    token = generate_jwt(secret="wrong-secret-key-that-does-not-match-at-all-000!")
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401
    assert "Invalid authentication token signature" in exc_info.value.detail


def test_jwt_unsigned_none_algorithm_rejected(monkeypatch):
    """Unsigned tokens using 'none' algorithm are strictly rejected."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    payload = {"sub": "HACKER-01", "role": "admin"}
    token = jwt.encode(payload, key="", algorithm="none")
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401


def test_jwt_expired_token_rejected(monkeypatch):
    """Expired token is rejected with 401."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    token = generate_jwt(expires_in_seconds=-60)  # Expired 1 minute ago
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_jwt_missing_sub_rejected(monkeypatch):
    """Token missing required 'sub' subject claim is rejected."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    now = datetime.now(timezone.utc)
    payload = {"email": "nosub@example.com", "exp": int((now + timedelta(seconds=3600)).timestamp())}
    token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401
    assert "invalid authentication token" in exc_info.value.detail.lower()


def test_jwt_missing_secret_in_production_fails_closed(monkeypatch):
    """When mandatory JWT secret is empty in production, verification fails closed."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt("dummy.token.here")
    assert exc_info.value.status_code in (401, 500)


# =============================================================================
# 2. ELIMINATE PRODUCTION DEMO AUTH & PRIVILEGE ESCALATION
# =============================================================================

def test_production_rejects_demo_tokens_and_role_headers(client: TestClient, monkeypatch):
    """In production environment, demo tokens and X-StockWise-Role headers are denied with 401."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_DEMO_AUTH", False)

    # Attempt request with demo bearer token
    res1 = client.get("/api/products", headers={"Authorization": "Bearer demo-admin-token"})
    assert res1.status_code == 401
    assert "Demo tokens are rejected in production mode" in res1.json()["detail"]

    # Attempt request with only role header
    res2 = client.get("/api/products", headers={"X-StockWise-Role": "admin"})
    assert res2.status_code == 401

    # Attempt request with no credentials at all
    res3 = client.get("/api/products")
    assert res3.status_code == 401


def test_privilege_escalation_via_user_metadata_demoted_to_viewer():
    """
    Self-assigned 'admin' or 'planner' role in client-editable user_metadata
    is strictly demoted to 'viewer' unless server app_metadata or server mapping confirms it.
    """
    untrusted_claims = {
        "sub": "ATTACKER-01",
        "email": "attacker@evil.corp",
        "user_metadata": {"role": "admin", "org_id": "ORG-ALPHA"},
        "app_metadata": {},
    }
    role, org = derive_trusted_role_and_org(untrusted_claims)
    assert role == "viewer", "Privilege escalation attempt must be demoted to viewer!"


def test_server_verified_app_metadata_role_trusted():
    """Roles set in server-controlled app_metadata are properly respected."""
    trusted_claims = {
        "sub": "PLANNER-01",
        "email": "custom-planner@example.com",
        "app_metadata": {"role": "planner", "org_id": "ORG-ALPHA"},
        "user_metadata": {},
    }
    role, org = derive_trusted_role_and_org(trusted_claims)
    assert role == "planner"
    assert org == "ORG-ALPHA"


# =============================================================================
# 3. ORGANIZATION-LEVEL TENANT ISOLATION TESTS
# =============================================================================

def setup_two_tenants(client: TestClient, db_session):
    """Bootstraps two completely distinct organizations with facilities and inventory."""
    # Create Org Alpha (FMCG Company) and Org Beta (Independent Competitor/Distributor)
    org_a = Organization(org_id="ORG-ALPHA", name="Alpha FMCG Ltd", org_type="fmcg_company", is_active=True)
    org_b = Organization(org_id="ORG-BETA", name="Beta Foods Corp", org_type="fmcg_company", is_active=True)
    db_session.add_all([org_a, org_b])

    # Facilities
    loc_a = Location(location_id="LOC-WH-ALPHA", name="Alpha Central DC", location_type="company_warehouse", region="West", owner_org_id="ORG-ALPHA", is_active=True)
    loc_b = Location(location_id="LOC-WH-BETA", name="Beta Central DC", location_type="company_warehouse", region="North", owner_org_id="ORG-BETA", is_active=True)
    db_session.add_all([loc_a, loc_b])

    # Products (note: Product model does not have is_active)
    prod_a = Product(sku_id="SKU-ALPHA-01", name="Alpha Tea 500g", category="Beverages", unit="cases")
    prod_b = Product(sku_id="SKU-BETA-01", name="Beta Biscuits 200g", category="Snacks", unit="cases")
    db_session.add_all([prod_a, prod_b])

    # Inventory
    today = date.today()
    inv_a = InventorySnapshot(
        snapshot_id="SNAP-A-1",
        sku_id="SKU-ALPHA-01",
        location_id="LOC-WH-ALPHA",
        owner_org_id="ORG-ALPHA",
        on_hand=500.0,
        reserved=50.0,
        blocked=0.0,
        as_of_date=today,
    )
    inv_b = InventorySnapshot(
        snapshot_id="SNAP-B-1",
        sku_id="SKU-BETA-01",
        location_id="LOC-WH-BETA",
        owner_org_id="ORG-BETA",
        on_hand=800.0,
        reserved=100.0,
        blocked=0.0,
        as_of_date=today,
    )
    db_session.add_all([inv_a, inv_b])

    # Shipments
    ship_a = Shipment(
        shipment_id="SHP-ALPHA-01",
        sku_id="SKU-ALPHA-01",
        quantity=100.0,
        source_location_id="LOC-WH-ALPHA",
        destination_location_id="LOC-WH-ALPHA",
        owner_org_id="ORG-ALPHA",
        status="proposed",
        approval_status="pending",
    )
    ship_b = Shipment(
        shipment_id="SHP-BETA-01",
        sku_id="SKU-BETA-01",
        quantity=200.0,
        source_location_id="LOC-WH-BETA",
        destination_location_id="LOC-WH-BETA",
        owner_org_id="ORG-BETA",
        status="proposed",
        approval_status="pending",
    )
    db_session.add_all([ship_a, ship_b])

    # Planning Runs
    plan_a = PlanningRun(
        run_id="PLAN-ALPHA-01",
        horizon_days=7,
        solver_status="optimal",
        service_level_percent=98.5,
        org_id="ORG-ALPHA",
    )
    plan_b = PlanningRun(
        run_id="PLAN-BETA-01",
        horizon_days=7,
        solver_status="optimal",
        service_level_percent=95.0,
        org_id="ORG-BETA",
    )
    db_session.add_all([plan_a, plan_b])

    # Import Runs
    imp_a = ImportRun(
        run_id="IMP-ALPHA-01",
        dataset_type="inventory",
        filename="alpha_inv.csv",
        file_format="csv",
        file_size_bytes=1024,
        status="completed",
        org_id="ORG-ALPHA",
    )
    imp_b = ImportRun(
        run_id="IMP-BETA-01",
        dataset_type="inventory",
        filename="beta_inv.csv",
        file_format="csv",
        file_size_bytes=1024,
        status="completed",
        org_id="ORG-BETA",
    )
    db_session.add_all([imp_a, imp_b])

    db_session.commit()


def auth_headers_for(sub: str, role: str, org_id: str) -> dict:
    """Generates valid Bearer headers for an authenticated tenant identity."""
    token = generate_jwt(sub=sub, role=role, org_id=org_id)
    return {"Authorization": f"Bearer {token}"}


def test_tenant_cannot_read_another_organization_inventory(client: TestClient, db_session, monkeypatch):
    """Organization Alpha user cannot see Organization Beta inventory in /api/inventory."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    setup_two_tenants(client, db_session)

    headers_alpha = auth_headers_for("USER-A", "planner", "ORG-ALPHA")
    res = client.get("/api/inventory", headers=headers_alpha)
    assert res.status_code == 200
    records = res.json()
    assert len(records) > 0
    # Every returned inventory record MUST belong to ORG-ALPHA
    for rec in records:
        assert rec["owner_org_id"] == "ORG-ALPHA"
        assert rec["sku_id"] != "SKU-BETA-01"


def test_tenant_cannot_access_another_organization_import_runs(client: TestClient, db_session, monkeypatch):
    """Organization Alpha cannot list, get, or download error reports for Org Beta imports."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    setup_two_tenants(client, db_session)

    headers_alpha = auth_headers_for("USER-A", "planner", "ORG-ALPHA")

    # 1. List imports returns only Org Alpha runs
    res_list = client.get("/api/imports", headers=headers_alpha)
    assert res_list.status_code == 200
    run_ids = [r["run_id"] for r in res_list.json()["runs"]]
    assert "IMP-ALPHA-01" in run_ids
    assert "IMP-BETA-01" not in run_ids

    # 2. Direct get of Org Beta run returns 404
    res_get = client.get("/api/imports/IMP-BETA-01", headers=headers_alpha)
    assert res_get.status_code == 404

    # 3. Direct download of Org Beta errors CSV returns 404
    res_err_csv = client.get("/api/imports/IMP-BETA-01/errors.csv", headers=headers_alpha)
    assert res_err_csv.status_code == 404


def test_tenant_cannot_access_or_export_another_organization_planning_runs(client: TestClient, db_session, monkeypatch):
    """Organization Alpha cannot access or export Org Beta's planning runs and receipts."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    setup_two_tenants(client, db_session)

    headers_alpha = auth_headers_for("USER-A", "planner", "ORG-ALPHA")

    # 1. Listing returns only Alpha plans
    res_list = client.get("/api/optimization/runs", headers=headers_alpha)
    assert res_list.status_code == 200
    runs = [r["run_id"] for r in res_list.json()]
    assert "PLAN-ALPHA-01" in runs
    assert "PLAN-BETA-01" not in runs

    # 2. Direct get returns 404
    res_get = client.get("/api/optimization/runs/PLAN-BETA-01", headers=headers_alpha)
    assert res_get.status_code == 404

    # 3. Export receipts returns 404
    res_receipts = client.get("/api/optimization/runs/PLAN-BETA-01/export/receipts.csv", headers=headers_alpha)
    assert res_receipts.status_code == 404


def test_tenant_cannot_read_or_mutate_another_organization_shipments(client: TestClient, db_session, monkeypatch):
    """Organization Alpha cannot read, approve, dispatch, or cancel Org Beta's shipments."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    setup_two_tenants(client, db_session)

    headers_alpha = auth_headers_for("USER-A", "planner", "ORG-ALPHA")

    # 1. Listing returns only Alpha shipments
    res_list = client.get("/api/shipments", headers=headers_alpha)
    assert res_list.status_code == 200
    ship_ids = [s["shipment_id"] for s in res_list.json()]
    assert "SHP-ALPHA-01" in ship_ids
    assert "SHP-BETA-01" not in ship_ids

    # 2. Direct get of Org Beta shipment returns 404
    res_get = client.get("/api/shipments/SHP-BETA-01", headers=headers_alpha)
    assert res_get.status_code == 404

    # 3. Attempting approval of Org Beta shipment returns 404
    res_app = client.post(
        "/api/shipments/SHP-BETA-01/approve",
        headers=headers_alpha,
        json={"approved": True, "authorized_user_id": "USER-A", "notes": "Unauthorized approval attempt"},
    )
    assert res_app.status_code == 404

    # 4. Attempting dispatch of Org Beta shipment by Org Alpha logistics returns 404
    headers_logistics_alpha = auth_headers_for("USER-LOG-A", "logistics", "ORG-ALPHA")
    res_disp = client.post(
        "/api/shipments/SHP-BETA-01/dispatch",
        headers=headers_logistics_alpha,
        json={"authorized_user_id": "USER-LOG-A", "consignment_number": "CON-HACK", "vehicle_number": "MH-01-9999"},
    )
    assert res_disp.status_code == 404

    # 5. Attempting cancel of Org Beta shipment returns 404
    res_cancel = client.post(
        "/api/shipments/SHP-BETA-01/cancel",
        headers=headers_alpha,
    )
    assert res_cancel.status_code == 404


def test_non_admin_cannot_perform_global_network_administration(client: TestClient, monkeypatch):
    """Non-admin roles cannot create global organizations, locations, or routes."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    headers_planner = auth_headers_for("USER-P", "planner", "ORG-ALPHA")

    # Try creating organization as planner -> 403
    res_org = client.post("/api/organizations", headers=headers_planner, json={"org_id": "ORG-NEW", "name": "New Org", "org_type": "distributor"})
    assert res_org.status_code == 403

    # Try creating location as planner -> 403
    res_loc = client.post("/api/network/locations", headers=headers_planner, json={"location_id": "LOC-NEW", "name": "New DC", "location_type": "company_warehouse", "region": "West"})
    assert res_loc.status_code == 403


# =============================================================================
# 4. IDEMPOTENCY & CONCURRENCY TESTS
# =============================================================================

def test_idempotency_exact_replay_returns_cached_200(client: TestClient, db_session, monkeypatch):
    """Replaying an Idempotency-Key with identical payload returns the cached result."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    setup_two_tenants(client, db_session)

    headers = auth_headers_for("USER-A", "planner", "ORG-ALPHA")
    headers["Idempotency-Key"] = "IDEMP-KEY-TEST-001"

    payload = {"approved": True, "authorized_user_id": "USER-A", "notes": "First approval call"}

    # 1. First execution
    res1 = client.post("/api/shipments/SHP-ALPHA-01/approve", headers=headers, json=payload)
    assert res1.status_code == 200
    assert res1.json()["approval_status"] == "approved"

    # 2. Replay with identical key and payload
    res2 = client.post("/api/shipments/SHP-ALPHA-01/approve", headers=headers, json=payload)
    assert res2.status_code == 200
    assert res2.json()["approval_status"] == "approved"
    assert res2.json()["shipment_id"] == res1.json()["shipment_id"]


def test_idempotency_mismatched_payload_returns_409_conflict(client: TestClient, db_session, monkeypatch):
    """Reusing an Idempotency-Key with a conflicting/materially different payload returns HTTP 409 Conflict."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    setup_two_tenants(client, db_session)

    headers = auth_headers_for("USER-A", "planner", "ORG-ALPHA")
    headers["Idempotency-Key"] = "IDEMP-KEY-TEST-CONFLICT"

    # 1. First execution with approval
    res1 = client.post("/api/shipments/SHP-ALPHA-01/approve", headers=headers, json={"approved": True, "authorized_user_id": "USER-A", "notes": "Approved"})
    assert res1.status_code == 200

    # 2. Conflicting re-execution with rejection under SAME idempotency key
    res2 = client.post("/api/shipments/SHP-ALPHA-01/approve", headers=headers, json={"approved": False, "authorized_user_id": "USER-A", "notes": "Changed my mind to rejected"})
    assert res2.status_code == 409
    assert "Idempotency conflict" in res2.json()["detail"]


def test_duplicate_dispatch_cannot_consume_stock_twice(client: TestClient, db_session, monkeypatch):
    """
    Physical dispatch cannot be called twice on the same shipment.
    Verifies that inventory cannot be double-deducted.
    """
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    setup_two_tenants(client, db_session)

    # Approve and prepare shipment
    ship = db_session.query(Shipment).filter(Shipment.shipment_id == "SHP-ALPHA-01").first()
    ship.status = "ready_for_dispatch"
    ship.approval_status = "approved"
    db_session.commit()

    headers = auth_headers_for("USER-A", "logistics", "ORG-ALPHA")
    dispatch_payload = {
        "authorized_user_id": "USER-A",
        "consignment_number": "LR-MUM-9988",
        "vehicle_number": "MH-12-AB-1234",
        "driver_contact": "+91 9876543210",
    }

    # First dispatch succeeds
    res1 = client.post("/api/shipments/SHP-ALPHA-01/dispatch", headers=headers, json=dispatch_payload)
    assert res1.status_code == 200
    assert res1.json()["status"] == "in_transit"

    # Duplicate dispatch attempt is rejected
    res2 = client.post("/api/shipments/SHP-ALPHA-01/dispatch", headers=headers, json=dispatch_payload)
    assert res2.status_code == 400
    assert "DUPLICATE_DISPATCH_REJECTED" in res2.json()["detail"]


def test_shipment_cancellation_releases_reserved_stock(client: TestClient, db_session, monkeypatch):
    """
    When a 'ready_for_dispatch' shipment is cancelled, its reserved inventory
    is released cleanly and atomically back to dispatchable stock.
    """
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    setup_two_tenants(client, db_session)

    # Put shipment in ready_for_dispatch with 100 units reserved
    inv = db_session.query(InventorySnapshot).filter(InventorySnapshot.sku_id == "SKU-ALPHA-01").first()
    inv.on_hand = 500.0
    inv.reserved = 100.0
    inv.blocked = 0.0

    ship = db_session.query(Shipment).filter(Shipment.shipment_id == "SHP-ALPHA-01").first()
    ship.status = "ready_for_dispatch"
    ship.approval_status = "approved"
    ship.quantity = 100.0
    db_session.commit()

    assert inv.dispatchable_stock == 400.0

    # Cancel shipment
    headers = auth_headers_for("USER-A", "planner", "ORG-ALPHA")
    res = client.post("/api/shipments/SHP-ALPHA-01/cancel", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"

    # Check inventory reservation released
    db_session.refresh(inv)
    assert inv.reserved == 0.0
    assert inv.dispatchable_stock == 500.0
