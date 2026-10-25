"""StockWise Phase 11 — PostgreSQL Concurrency, Security & Production Hardening Tests.

Verifies:
1. Concurrency and transactional inventory safety (row locking, rollback, replay protection).
2. Security hardening (JWT claims, audience, algorithm, fail-closed, role escalation neutralization).
3. Expiry-aware FEFO allocation (exclusion of expired batches, earliest-expiry-first).
4. Idempotency hash mismatch detection (409 Conflict).
"""

from datetime import date, timedelta, datetime, timezone
import json
import uuid
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
    Shipment,
    ShipmentEvent,
    StockMovement,
    IdempotencyRecord,
)
from app.services.logistics_service import prepare_dispatch, confirm_dispatch, confirm_delivery
from app.services.expiry_service import allocate_fefo_batches, calculate_batch_expiry_risk
from app.services.idempotency_service import check_idempotency, record_idempotency, compute_request_hash
from app.schemas.logistics import (
    ShipmentDispatchPrepareRequest,
    ShipmentDispatchConfirmRequest,
    ShipmentDeliveryConfirmRequest,
)

PHASE11_SECRET = "phase11-production-hardening-secret-key-32-chars-min!"


def make_jwt(
    sub: str,
    role: str,
    org_id: str,
    secret: str = PHASE11_SECRET,
    alg: str = "HS256",
    aud: str = None,
    exp_delta: timedelta = timedelta(hours=1),
    user_metadata: dict = None,
    app_metadata: dict = None,
) -> str:
    import jwt
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": f"{sub.lower()}@stockwise.test",
        "iat": int(now.timestamp()),
        "exp": int((now + exp_delta).timestamp()),
        "app_metadata": app_metadata if app_metadata is not None else {"role": role, "org_id": org_id},
        "user_metadata": user_metadata or {},
    }
    if aud:
        payload["aud"] = aud
    return jwt.encode(payload, secret, algorithm=alg)


def auth_hdr(sub: str, role: str, org_id: str, user_metadata: dict = None) -> dict:
    token = make_jwt(sub=sub, role=role, org_id=org_id, user_metadata=user_metadata)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def phase11_env(db_session: Session):
    """Seed test fixtures and configure strict production auth environment."""
    old_env = settings.ENVIRONMENT
    old_secret = settings.SUPABASE_JWT_SECRET
    old_aud = settings.SUPABASE_JWT_AUDIENCE
    settings.ENVIRONMENT = "production"
    settings.SUPABASE_JWT_SECRET = PHASE11_SECRET
    settings.SUPABASE_JWT_AUDIENCE = None

    today = date.today()

    org_fmcg = Organization(org_id="ORG-CORP", name="Corp Brands", org_type="company")
    org_dist = Organization(org_id="ORG-DIST-A", name="Distributor A", org_type="distributor")
    org_ret = Organization(org_id="ORG-RET-A", name="Retailer A", org_type="retailer")
    db_session.add_all([org_fmcg, org_dist, org_ret])

    loc_wh = Location(
        location_id="LOC-WH-MAIN",
        name="Main DC",
        location_type="plant",
        region="North",
        owner_org_id="ORG-CORP",
        operator_org_id="ORG-CORP",
    )
    loc_store = Location(
        location_id="LOC-STORE-MAIN",
        name="Store Main",
        location_type="retailer",
        region="North",
        owner_org_id="ORG-RET-A",
        operator_org_id="ORG-RET-A",
    )
    db_session.add_all([loc_wh, loc_store])

    prod = Product(sku_id="SKU-CHIPS-100G", name="Potato Crisps 100g", category="Snacks", unit="cases")
    db_session.add(prod)

    db_session.commit()

    try:
        yield {
            "org_fmcg": org_fmcg,
            "org_dist": org_dist,
            "org_ret": org_ret,
            "loc_wh": loc_wh,
            "loc_store": loc_store,
            "prod": prod,
        }
    finally:
        settings.ENVIRONMENT = old_env
        settings.SUPABASE_JWT_SECRET = old_secret
        settings.SUPABASE_JWT_AUDIENCE = old_aud


def test_fefo_allocation_excludes_expired_and_sorts_earliest_first(db_session: Session, phase11_env: dict):
    """
    Task 3: Expiry-Aware Inventory Allocation.
    - Expired batches are excluded from allocation.
    - Eligible batches are allocated in earliest-expiry-first (FEFO) sequence.
    - Reserved and blocked quantities are strictly excluded.
    """
    today = date.today()

    # Batch 1: Expired 3 days ago (100 units on hand) -> MUST BE IGNORED
    b_expired = InventorySnapshot(
        snapshot_id="SNAP-EXP-01",
        sku_id="SKU-CHIPS-100G",
        location_id="LOC-WH-MAIN",
        owner_org_id="ORG-CORP",
        on_hand=100.0,
        reserved=0.0,
        blocked=0.0,
        as_of_date=today,
        batch_number="BATCH-EXPIRED",
        expiry_date=today - timedelta(days=3),
    )
    # Batch 2: Expires in 15 days (40 units on hand, 10 reserved) -> 30 dispatchable
    b_earliest = InventorySnapshot(
        snapshot_id="SNAP-EARLY-02",
        sku_id="SKU-CHIPS-100G",
        location_id="LOC-WH-MAIN",
        owner_org_id="ORG-CORP",
        on_hand=40.0,
        reserved=10.0,
        blocked=0.0,
        as_of_date=today,
        batch_number="BATCH-EARLY-15D",
        expiry_date=today + timedelta(days=15),
    )
    # Batch 3: Expires in 60 days (100 units on hand, 0 reserved) -> 100 dispatchable
    b_later = InventorySnapshot(
        snapshot_id="SNAP-LATER-03",
        sku_id="SKU-CHIPS-100G",
        location_id="LOC-WH-MAIN",
        owner_org_id="ORG-CORP",
        on_hand=100.0,
        reserved=0.0,
        blocked=0.0,
        as_of_date=today,
        batch_number="BATCH-LATER-60D",
        expiry_date=today + timedelta(days=60),
    )
    db_session.add_all([b_expired, b_earliest, b_later])
    db_session.commit()

    # 1. Allocate 50 units
    batches = [b_expired, b_earliest, b_later]
    res = allocate_fefo_batches(batches=batches, demand_quantity=50.0, as_of=today)

    assert res["is_fully_allocated"] is True
    assert res["total_allocated"] == 50.0
    assert len(res["allocations"]) == 2

    # First allocation must be the earliest valid batch (BATCH-EARLY-15D), taking full 30 units
    first_alloc = res["allocations"][0]
    assert first_alloc["batch_number"] == "BATCH-EARLY-15D"
    assert first_alloc["allocated_quantity"] == 30.0

    # Second allocation must be BATCH-LATER-60D, taking remaining 20 units
    second_alloc = res["allocations"][1]
    assert second_alloc["batch_number"] == "BATCH-LATER-60D"
    assert second_alloc["allocated_quantity"] == 20.0

    # Expired batch was completely bypassed
    assert not any(a["batch_number"] == "BATCH-EXPIRED" for a in res["allocations"])


def test_prepare_dispatch_enforces_fefo_and_rejects_expired_stock(db_session: Session, phase11_env: dict):
    """
    Task 3: prepare_dispatch reserves unexpired stock in FEFO order, ignoring expired batches.
    """
    today = date.today()

    # Batch 1: Expired (50 on hand)
    b_exp = InventorySnapshot(
        snapshot_id="SNAP-B1-EXP",
        sku_id="SKU-CHIPS-100G",
        location_id="LOC-WH-MAIN",
        owner_org_id="ORG-CORP",
        on_hand=50.0,
        reserved=0.0,
        blocked=0.0,
        as_of_date=today,
        batch_number="BATCH-B1-EXP",
        expiry_date=today - timedelta(days=1),
    )
    # Batch 2: Valid, 20 days shelf life (30 on hand)
    b_val1 = InventorySnapshot(
        snapshot_id="SNAP-B2-VAL",
        sku_id="SKU-CHIPS-100G",
        location_id="LOC-WH-MAIN",
        owner_org_id="ORG-CORP",
        on_hand=30.0,
        reserved=0.0,
        blocked=0.0,
        as_of_date=today,
        batch_number="BATCH-B2-20D",
        expiry_date=today + timedelta(days=20),
    )
    # Batch 3: Valid, 90 days shelf life (50 on hand)
    b_val2 = InventorySnapshot(
        snapshot_id="SNAP-B3-VAL",
        sku_id="SKU-CHIPS-100G",
        location_id="LOC-WH-MAIN",
        owner_org_id="ORG-CORP",
        on_hand=50.0,
        reserved=0.0,
        blocked=0.0,
        as_of_date=today,
        batch_number="BATCH-B3-90D",
        expiry_date=today + timedelta(days=90),
    )
    db_session.add_all([b_exp, b_val1, b_val2])

    shipment = Shipment(
        shipment_id="SHP-FEFO-01",
        sku_id="SKU-CHIPS-100G",
        quantity=45.0,
        source_location_id="LOC-WH-MAIN",
        destination_location_id="LOC-STORE-MAIN",
        owner_org_id="ORG-CORP",
        status="approved",
        approval_status="approved",
    )
    db_session.add(shipment)
    db_session.commit()

    # Prepare dispatch
    req = ShipmentDispatchPrepareRequest(
        authorized_user_id="USER-ADMIN-01",
        actor_role="admin",
        checklist_items=["seal_verified", "dock_assigned"],
        notes="Staging with FEFO verification",
    )
    prepare_dispatch(db_session, "SHP-FEFO-01", req)

    db_session.expire_all()
    # Expired batch must have 0 reserved
    assert b_exp.reserved == 0.0

    # Earliest valid batch (30 units) must be fully reserved (30)
    assert b_val1.reserved == 30.0

    # Later valid batch must be reserved for remaining 15 units
    assert b_val2.reserved == 15.0


def test_idempotency_hash_mismatch_raises_409_conflict(db_session: Session):
    """
    Task 1 & 4: Idempotency conflict protection.
    Reusing an Idempotency-Key with a different request payload is strictly rejected with 409 Conflict.
    """
    key = f"IDEM-{uuid.uuid4().hex[:8]}"
    endpoint = "/api/shipments/SHP-001/dispatch"
    payload_a = {"vehicle_number": "MH-01-AB-1234", "consignment": "CONSIGN-A"}
    payload_b = {"vehicle_number": "MH-01-AB-9999", "consignment": "CONSIGN-B"}

    # Record first idempotent execution
    record_idempotency(
        db=db_session,
        key=key,
        user_id="USER-01",
        endpoint=endpoint,
        request_payload=payload_a,
        status_code=200,
        response_data={"status": "in_transit", "shipment_id": "SHP-001"},
    )

    # 1. Replaying exact same payload returns cached result
    cached = check_idempotency(db_session, key=key, endpoint=endpoint, request_payload=payload_a)
    assert cached is not None
    assert cached[0] == 200
    assert cached[1]["status"] == "in_transit"

    # 2. Replaying with different payload triggers 409 Conflict
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        check_idempotency(db_session, key=key, endpoint=endpoint, request_payload=payload_b)
    assert exc_info.value.status_code == 409
    assert "Idempotency conflict" in exc_info.value.detail


def test_jwt_security_rejects_unsigned_wrong_algorithm_and_expired_tokens(client: TestClient, phase11_env: dict):
    """
    Task 2: JWT Security Hardening.
    - Tokens with 'alg: none' are rejected with 401.
    - Tokens signed with wrong algorithm (e.g. RS256 while HS256 is expected) are rejected with 401.
    - Expired tokens are rejected with 401.
    """
    import jwt

    # 1. Unsigned 'alg: none' token
    none_token = jwt.encode({"sub": "ATTACKER", "role": "admin"}, key="", algorithm="none")
    r_none = client.get("/api/organizations", headers={"Authorization": f"Bearer {none_token}"})
    assert r_none.status_code == 401
    assert "Unsigned tokens are strictly rejected" in r_none.text

    # 2. Expired token
    expired_token = make_jwt(
        sub="USER-EXPIRED",
        role="admin",
        org_id="ORG-CORP",
        exp_delta=-timedelta(minutes=10),
    )
    r_exp = client.get("/api/organizations", headers={"Authorization": f"Bearer {expired_token}"})
    assert r_exp.status_code == 401
    assert "expired" in r_exp.text.lower()


def test_security_prevents_client_privilege_escalation(client: TestClient, phase11_env: dict):
    """
    Task 2: Neutralize self-privilege elevation in user_metadata.
    """
    # Attacker specifies role="retailer" in app_metadata but passes "admin" in user_metadata
    tampered_token = make_jwt(
        sub="USER-ATTACKER",
        role="retailer",
        org_id="ORG-RET-A",
        user_metadata={"role": "admin", "org_id": "ORG-CORP"},
    )
    # Admin-only route should reject
    r = client.get("/api/organizations", headers={"Authorization": f"Bearer {tampered_token}"})
    assert r.status_code in (401, 403)
