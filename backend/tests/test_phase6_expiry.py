from datetime import date, timedelta, datetime, timezone
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.entities import Product, Location, InventorySnapshot, Organization
from app.services.expiry_service import (
    calculate_batch_expiry_risk,
    summarize_expiry_risk,
    allocate_fefo_batches,
)

TEST_SECRET = "test-phase6-secret-must-be-at-least-32-chars-long!"


def generate_jwt(sub: str, role: str, org_id: str, secret: str = TEST_SECRET) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": f"{sub.lower()}@stockwise.internal",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "app_metadata": {"role": role, "org_id": org_id},
        "user_metadata": {},
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def auth_headers(sub: str, role: str, org_id: str) -> dict:
    token = generate_jwt(sub=sub, role=role, org_id=org_id)
    return {"Authorization": f"Bearer {token}"}


class MockBatch:
    def __init__(self, snapshot_id, sku_id, on_hand, reserved, blocked, expiry_date, batch_number=None, location_id="LOC-1", id=1):
        self.id = id
        self.snapshot_id = snapshot_id
        self.sku_id = sku_id
        self.location_id = location_id
        self.on_hand = float(on_hand)
        self.reserved = float(reserved)
        self.blocked = float(blocked)
        self.expiry_date = expiry_date
        self.batch_number = batch_number
        self.owner_org_id = "ORG-1"
        self.product = None
        self.location = None


# =============================================================================
# 1. UNIT TESTS FOR EXPIRY RISK AND FEFO ALLOCATION ENGINE
# =============================================================================

def test_earliest_eligible_expiry_prioritized():
    """Batches with earlier expiry dates must be allocated before batches with later expiry."""
    today = date(2026, 10, 25)
    b_late = MockBatch("SNAP-LATE", "SKU-TEA", on_hand=100, reserved=0, blocked=0, expiry_date=today + timedelta(days=60), batch_number="B-LATE", id=1)
    b_early = MockBatch("SNAP-EARLY", "SKU-TEA", on_hand=100, reserved=0, blocked=0, expiry_date=today + timedelta(days=10), batch_number="B-EARLY", id=2)

    res = allocate_fefo_batches([b_late, b_early], demand_quantity=50, as_of=today)

    assert res["is_fully_allocated"] is True
    assert res["total_allocated"] == 50.0
    assert len(res["allocations"]) == 1
    # Early batch must be chosen first
    assert res["allocations"][0]["batch_number"] == "B-EARLY"
    assert res["allocations"][0]["allocated_quantity"] == 50.0


def test_expired_batches_strictly_excluded():
    """Batches whose expiry date has already passed must never be allocated or considered dispatchable."""
    today = date(2026, 10, 25)
    b_expired = MockBatch("SNAP-EXP", "SKU-MILK", on_hand=100, reserved=0, blocked=0, expiry_date=today - timedelta(days=2), batch_number="B-EXP", id=1)
    b_valid = MockBatch("SNAP-VAL", "SKU-MILK", on_hand=40, reserved=0, blocked=0, expiry_date=today + timedelta(days=5), batch_number="B-VAL", id=2)

    # 1. Check risk calculation
    risk_exp = calculate_batch_expiry_risk(b_expired, as_of=today)
    assert risk_exp["risk_category"] == "expired"
    assert risk_exp["is_dispatchable"] is False

    # 2. Check allocation strictly excludes expired batch
    res = allocate_fefo_batches([b_expired, b_valid], demand_quantity=60, as_of=today)
    assert res["total_allocated"] == 40.0
    assert res["unmet_demand"] == 20.0
    assert len(res["allocations"]) == 1
    assert res["allocations"][0]["batch_number"] == "B-VAL"


def test_blocked_and_reserved_quantities_respected():
    """Dispatchable quantity = max(0, on_hand - reserved - blocked). Fully blocked/reserved batches excluded."""
    today = date(2026, 10, 25)
    # 100 on_hand but 70 reserved + 30 blocked = 0 dispatchable
    b_blocked = MockBatch("SNAP-BLK", "SKU-OIL", on_hand=100, reserved=70, blocked=30, expiry_date=today + timedelta(days=20), batch_number="B-BLK", id=1)
    # 100 on_hand, 20 reserved, 10 blocked = 70 dispatchable
    b_avail = MockBatch("SNAP-AVL", "SKU-OIL", on_hand=100, reserved=20, blocked=10, expiry_date=today + timedelta(days=25), batch_number="B-AVL", id=2)

    res = allocate_fefo_batches([b_blocked, b_avail], demand_quantity=50, as_of=today)
    assert res["total_allocated"] == 50.0
    assert len(res["allocations"]) == 1
    assert res["allocations"][0]["batch_number"] == "B-AVL"
    assert res["allocations"][0]["available_before_allocation"] == 70.0
    assert res["allocations"][0]["remaining_after_allocation"] == 20.0


def test_insufficient_stock_produces_unmet_demand():
    """When demand exceeds available dispatchable stock across all batches, unmet demand is explicitly reported."""
    today = date(2026, 10, 25)
    b1 = MockBatch("SNAP-1", "SKU-SOAP", on_hand=30, reserved=0, blocked=0, expiry_date=today + timedelta(days=15), batch_number="B-1", id=1)
    b2 = MockBatch("SNAP-2", "SKU-SOAP", on_hand=20, reserved=0, blocked=0, expiry_date=today + timedelta(days=30), batch_number="B-2", id=2)

    res = allocate_fefo_batches([b1, b2], demand_quantity=75, as_of=today)
    assert res["is_fully_allocated"] is False
    assert res["total_allocated"] == 50.0
    assert res["unmet_demand"] == 25.0
    assert len(res["allocations"]) == 2


def test_missing_expiry_remains_unknown():
    """Batches without an expiry date must have days_remaining=None, category='unknown', and no fabricated shelf life."""
    today = date(2026, 10, 25)
    b_unknown = MockBatch("SNAP-UNK", "SKU-SALT", on_hand=100, reserved=0, blocked=0, expiry_date=None, batch_number="B-UNK", id=1)

    risk = calculate_batch_expiry_risk(b_unknown, as_of=today)
    assert risk["days_remaining"] is None
    assert risk["risk_category"] == "unknown"
    assert risk["expiry_date"] is None
    assert risk["dispatchable_quantity"] == 100.0
    assert risk["is_dispatchable"] is True


def test_min_remaining_shelf_life_respected():
    """Batches not meeting minimum remaining shelf life criteria are skipped."""
    today = date(2026, 10, 25)
    # 10 days shelf life remaining
    b_short = MockBatch("SNAP-SHORT", "SKU-BISCUIT", on_hand=50, reserved=0, blocked=0, expiry_date=today + timedelta(days=10), batch_number="B-SHORT", id=1)
    # 45 days shelf life remaining
    b_long = MockBatch("SNAP-LONG", "SKU-BISCUIT", on_hand=50, reserved=0, blocked=0, expiry_date=today + timedelta(days=45), batch_number="B-LONG", id=2)

    # Require at least 20 days shelf life
    res = allocate_fefo_batches([b_short, b_long], demand_quantity=30, min_remaining_shelf_life_days=20, as_of=today)
    assert res["total_allocated"] == 30.0
    assert len(res["allocations"]) == 1
    assert res["allocations"][0]["batch_number"] == "B-LONG"


# =============================================================================
# 2. API & TENANT ISOLATION INTEGRATION TESTS
# =============================================================================

def setup_expiry_test_db(db_session: Session):
    """Seed test data for two distinct organizations with batch expiry records."""
    org1 = Organization(org_id="ORG-EXP-A", name="Brand A FMCG", org_type="fmcg_company", is_active=True)
    org2 = Organization(org_id="ORG-EXP-B", name="Brand B Competitor", org_type="fmcg_company", is_active=True)
    db_session.add_all([org1, org2])

    loc_a = Location(location_id="LOC-EXP-A", name="A Warehouse", location_type="company_warehouse", region="West", owner_org_id="ORG-EXP-A")
    loc_b = Location(location_id="LOC-EXP-B", name="B Warehouse", location_type="company_warehouse", region="North", owner_org_id="ORG-EXP-B")
    db_session.add_all([loc_a, loc_b])

    prod = Product(sku_id="SKU-EXP-01", name="Premium Basmati Rice 5kg", category="Grains", unit="bags")
    db_session.add(prod)

    today = date.today()
    # Org A: Batch 1 expiring in 10 days, Batch 2 expiring in 40 days
    inv_a1 = InventorySnapshot(
        snapshot_id="SNAP-EA-1", sku_id="SKU-EXP-01", location_id="LOC-EXP-A",
        owner_org_id="ORG-EXP-A", on_hand=100.0, reserved=10.0, blocked=0.0,
        batch_number="BATCH-EA-10D", expiry_date=today + timedelta(days=10), as_of_date=today
    )
    inv_a2 = InventorySnapshot(
        snapshot_id="SNAP-EA-2", sku_id="SKU-EXP-01", location_id="LOC-EXP-A",
        owner_org_id="ORG-EXP-A", on_hand=200.0, reserved=0.0, blocked=0.0,
        batch_number="BATCH-EA-40D", expiry_date=today + timedelta(days=40), as_of_date=today
    )

    # Org B: Competitor batch
    inv_b1 = InventorySnapshot(
        snapshot_id="SNAP-EB-1", sku_id="SKU-EXP-01", location_id="LOC-EXP-B",
        owner_org_id="ORG-EXP-B", on_hand=500.0, reserved=0.0, blocked=0.0,
        batch_number="BATCH-EB-SECRET", expiry_date=today + timedelta(days=5), as_of_date=today
    )
    db_session.add_all([inv_a1, inv_a2, inv_b1])
    db_session.commit()


def test_api_expiry_risk_tenant_isolated(client: TestClient, db_session: Session, monkeypatch):
    """User in Org A can only see Org A batches in GET /api/inventory/expiry-risk."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    setup_expiry_test_db(db_session)

    headers_a = auth_headers("USER-A", "planner", "ORG-EXP-A")
    res = client.get("/api/inventory/expiry-risk", headers=headers_a)
    assert res.status_code == 200
    data = res.json()

    assert data["total_batches"] == 2
    batch_numbers = [item["batch_number"] for item in data["items"]]
    assert "BATCH-EA-10D" in batch_numbers
    assert "BATCH-EA-40D" in batch_numbers
    assert "BATCH-EB-SECRET" not in batch_numbers
    # Org A Batch 1 has <= 15 days so critical_batches must be 1
    assert data["critical_batches"] == 1


def test_api_fefo_allocation_tenant_isolated(client: TestClient, db_session: Session, monkeypatch):
    """FEFO allocation endpoint prioritizes earliest batch and cannot allocate from competitor org."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    setup_expiry_test_db(db_session)

    headers_a = auth_headers("USER-A", "planner", "ORG-EXP-A")
    payload = {
        "sku_id": "SKU-EXP-01",
        "demand_quantity": 120.0,
    }
    res = client.post("/api/inventory/fefo-allocate", headers=headers_a, json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["is_fully_allocated"] is True
    assert data["total_allocated"] == 120.0
    # First allocation: 90 units from BATCH-EA-10D (100 on_hand - 10 reserved = 90 dispatchable)
    assert data["allocations"][0]["batch_number"] == "BATCH-EA-10D"
    assert data["allocations"][0]["allocated_quantity"] == 90.0
    # Second allocation: 30 units from BATCH-EA-40D
    assert data["allocations"][1]["batch_number"] == "BATCH-EA-40D"
    assert data["allocations"][1]["allocated_quantity"] == 30.0
    # No allocation from competitor BATCH-EB-SECRET
    for alloc in data["allocations"]:
        assert alloc["batch_number"] != "BATCH-EB-SECRET"


def test_existing_inventory_api_remains_compatible(client: TestClient, db_session: Session, monkeypatch):
    """Existing GET /api/inventory returns dispatchable stock and batch/expiry fields without breakage."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    setup_expiry_test_db(db_session)

    headers_a = auth_headers("USER-A", "planner", "ORG-EXP-A")
    res = client.get("/api/inventory", headers=headers_a)
    assert res.status_code == 200
    records = res.json()
    assert len(records) == 2
    for r in records:
        assert r["owner_org_id"] == "ORG-EXP-A"
        assert "dispatchable_stock" in r
        assert "batch_number" in r
        assert "expiry_date" in r
