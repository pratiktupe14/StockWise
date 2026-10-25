from datetime import date, timedelta, datetime, timezone
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.entities import Product, Location, InventorySnapshot, Organization, Route, SalesHistory, Shipment, StockMovement
from app.services.redistribution_service import (
    generate_redistribution_recommendations,
    create_redistribution_shipment_proposal,
)
from app.schemas.redistribution import CreateRedistributionProposalRequest
from app.core.security import AuthenticatedUser

TEST_SECRET = "test-phase7-secret-must-be-at-least-32-chars-long!"


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


@pytest.fixture
def setup_redistribution_network(db_session: Session):
    """
    Sets up two distinct organizations:
    - ORG-REDIST-A: FMCG Company with Source WH and Destination DC, plus active route.
    - ORG-REDIST-B: Competitor / Independent with separate stock.
    """
    org_a = Organization(org_id="ORG-REDIST-A", name="Alpha FMCG Brands", org_type="fmcg_company", is_active=True)
    org_b = Organization(org_id="ORG-REDIST-B", name="Beta Competitor", org_type="fmcg_company", is_active=True)
    db_session.add_all([org_a, org_b])

    # Facilities
    loc_src = Location(location_id="LOC-WH-MUMBAI", name="Mumbai Central DC", location_type="company_warehouse", region="West", owner_org_id="ORG-REDIST-A", is_active=True)
    loc_dest = Location(location_id="LOC-DC-PUNE", name="Pune Regional DC", location_type="regional_dc", region="West", owner_org_id="ORG-REDIST-A", is_active=True)
    loc_comp = Location(location_id="LOC-WH-DELHI", name="Delhi Competitor Hub", location_type="company_warehouse", region="North", owner_org_id="ORG-REDIST-B", is_active=True)
    db_session.add_all([loc_src, loc_dest, loc_comp])

    # Product
    prod = Product(sku_id="SKU-CHOC-01", name="Deluxe Dark Chocolate 100g", category="Confectionery", unit="cases")
    db_session.add(prod)

    # Active transport route Mumbai -> Pune: lead time 2 days, cost ₹15.0 per case
    route_mum_pun = Route(
        from_location_id="LOC-WH-MUMBAI",
        to_location_id="LOC-DC-PUNE",
        lead_time_days=2.0,
        cost_rate=15.0,
        is_active=True,
    )
    db_session.add(route_mum_pun)

    # Sales history at Pune DC: average 10 cases/day -> 14-day target demand = 140 cases
    today = date.today()
    for i in range(1, 15):
        sale = SalesHistory(
            sku_id="SKU-CHOC-01",
            destination_id="LOC-DC-PUNE",
            sales_date=today - timedelta(days=i),
            quantity=10.0,
        )
        db_session.add(sale)

    # Org A: Source Mumbai has 200 units, near expiry (25 days left)
    inv_src = InventorySnapshot(
        snapshot_id="SNAP-SRC-MUM",
        sku_id="SKU-CHOC-01",
        location_id="LOC-WH-MUMBAI",
        owner_org_id="ORG-REDIST-A",
        on_hand=200.0,
        reserved=20.0,
        blocked=0.0,
        batch_number="BATCH-MUM-25D",
        expiry_date=today + timedelta(days=25),
        as_of_date=today,
    )

    # Org A: Destination Pune has only 40 units in stock -> shortfall = 140 - 40 = 100 cases
    inv_dest = InventorySnapshot(
        snapshot_id="SNAP-DEST-PUN",
        sku_id="SKU-CHOC-01",
        location_id="LOC-DC-PUNE",
        owner_org_id="ORG-REDIST-A",
        on_hand=40.0,
        reserved=0.0,
        blocked=0.0,
        batch_number="BATCH-PUN-OLD",
        expiry_date=today + timedelta(days=50),
        as_of_date=today,
    )

    # Org B: Competitor stock at Delhi
    inv_comp = InventorySnapshot(
        snapshot_id="SNAP-COMP-DEL",
        sku_id="SKU-CHOC-01",
        location_id="LOC-WH-DELHI",
        owner_org_id="ORG-REDIST-B",
        on_hand=500.0,
        reserved=0.0,
        blocked=0.0,
        batch_number="BATCH-COMP-SECRET",
        expiry_date=today + timedelta(days=20),
        as_of_date=today,
    )

    db_session.add_all([inv_src, inv_dest, inv_comp])
    db_session.commit()


# =============================================================================
# 1. CORE REDISTRIBUTION CANDIDATE GENERATION & RANKING TESTS
# =============================================================================

def test_surplus_near_expiry_generates_recommendation(db_session: Session, setup_redistribution_network):
    """
    Near-expiry stock (25d) at Mumbai (180 dispatchable) paired with Pune (shortfall 100)
    generates a concrete recommendation capped at 100 units.
    """
    user_a = AuthenticatedUser(user_id="USER-A", role="planner", org_id="ORG-REDIST-A")
    res = generate_redistribution_recommendations(db_session, user_a)

    assert res["recommendations_count"] >= 1
    rec = res["recommendations"][0]
    assert rec.sku_id == "SKU-CHOC-01"
    assert rec.source_location_id == "LOC-WH-MUMBAI"
    assert rec.destination_location_id == "LOC-DC-PUNE"
    # Capped at destination unmet demand: min(180, 100) = 100
    assert rec.recommended_quantity == 100.0
    # Lead time 2 days -> ETA today + 2d
    assert rec.lead_time_days == 2.0
    # Shelf life at arrival = 25 - 2 = 23 days
    assert rec.shelf_life_days_at_arrival == 23
    # Transport cost = 100 * ₹15 = ₹1,500
    assert rec.estimated_transport_cost == 1500.0
    assert rec.priority_score > 50.0
    assert "LOC-WH-MUMBAI" in rec.rationale


def test_expired_or_blocked_stock_rejected(db_session: Session, setup_redistribution_network):
    """Expired or quality blocked batches are strictly excluded from recommendation generation."""
    today = date.today()
    # Add expired batch to Mumbai
    inv_exp = InventorySnapshot(
        snapshot_id="SNAP-SRC-EXP",
        sku_id="SKU-CHOC-01",
        location_id="LOC-WH-MUMBAI",
        owner_org_id="ORG-REDIST-A",
        on_hand=50.0,
        reserved=0.0,
        blocked=0.0,
        batch_number="BATCH-EXPIRED",
        expiry_date=today - timedelta(days=1),
        as_of_date=today,
    )
    # Add fully blocked batch to Mumbai
    inv_blk = InventorySnapshot(
        snapshot_id="SNAP-SRC-BLK",
        sku_id="SKU-CHOC-01",
        location_id="LOC-WH-MUMBAI",
        owner_org_id="ORG-REDIST-A",
        on_hand=80.0,
        reserved=0.0,
        blocked=80.0,
        batch_number="BATCH-BLOCKED",
        expiry_date=today + timedelta(days=30),
        as_of_date=today,
    )
    db_session.add_all([inv_exp, inv_blk])
    db_session.commit()

    user_a = AuthenticatedUser(user_id="USER-A", role="planner", org_id="ORG-REDIST-A")
    res = generate_redistribution_recommendations(db_session, user_a)

    recommended_batches = [r.batch_number for r in res["recommendations"]]
    assert "BATCH-EXPIRED" not in recommended_batches
    assert "BATCH-BLOCKED" not in recommended_batches

    rejected_reasons = [rej.rejection_reason for rej in res["rejected_candidates"]]
    assert any("expired" in r.lower() for r in rejected_reasons)
    assert any("no dispatchable stock" in r.lower() for r in rejected_reasons)


def test_inadequate_remaining_shelf_life_rejects_candidate(db_session: Session, setup_redistribution_network):
    """
    If a batch expires before arrival or has less than 10 days shelf life upon arrival,
    it is rejected.
    """
    today = date.today()
    # Expiring in 8 days -> with 2 days lead time, shelf life at arrival is only 6 days (< 10 days minimum)
    inv_short = InventorySnapshot(
        snapshot_id="SNAP-SHORT-LIFE",
        sku_id="SKU-CHOC-01",
        location_id="LOC-WH-MUMBAI",
        owner_org_id="ORG-REDIST-A",
        on_hand=50.0,
        reserved=0.0,
        blocked=0.0,
        batch_number="BATCH-SHORT-6D",
        expiry_date=today + timedelta(days=8),
        as_of_date=today,
    )
    db_session.add(inv_short)
    db_session.commit()

    user_a = AuthenticatedUser(user_id="USER-A", role="planner", org_id="ORG-REDIST-A")
    res = generate_redistribution_recommendations(db_session, user_a)

    recommended_batches = [r.batch_number for r in res["recommendations"]]
    assert "BATCH-SHORT-6D" not in recommended_batches

    rejected = [rej for rej in res["rejected_candidates"] if rej.batch_number == "BATCH-SHORT-6D"]
    assert len(rejected) > 0
    assert "Insufficient shelf life" in rejected[0].rejection_reason


def test_recommendation_does_not_alter_physical_stock(db_session: Session, setup_redistribution_network):
    """Calling redistribution candidate generation is strictly read-only and alters no physical stock or reservations."""
    src_before = db_session.query(InventorySnapshot).filter(InventorySnapshot.snapshot_id == "SNAP-SRC-MUM").first()
    oh_before = src_before.on_hand
    res_before = src_before.reserved

    user_a = AuthenticatedUser(user_id="USER-A", role="planner", org_id="ORG-REDIST-A")
    generate_redistribution_recommendations(db_session, user_a)

    db_session.refresh(src_before)
    assert src_before.on_hand == oh_before
    assert src_before.reserved == res_before


# =============================================================================
# 2. PROPOSAL CREATION & SHIPMENT LIFECYCLE INTEGRATION TESTS
# =============================================================================

def test_create_redistribution_proposal_integrates_with_shipments(db_session: Session, setup_redistribution_network):
    """
    Accepting a recommendation submits a formal Shipment in 'proposed' state,
    creating a trace in StockMovements and ShipmentEvents without auto-dispatching.
    """
    user_a = AuthenticatedUser(user_id="USER-A", role="planner", org_id="ORG-REDIST-A")
    payload = CreateRedistributionProposalRequest(
        sku_id="SKU-CHOC-01",
        source_location_id="LOC-WH-MUMBAI",
        destination_location_id="LOC-DC-PUNE",
        quantity=60.0,
        batch_number="BATCH-MUM-25D",
        notes="Authorized expiry prevention transfer to Pune DC",
    )

    shipment = create_redistribution_shipment_proposal(db_session, user_a, payload)

    assert shipment.shipment_id.startswith("SHP-")
    assert shipment.sku_id == "SKU-CHOC-01"
    assert shipment.quantity == 60.0
    assert shipment.status == "proposed"
    assert shipment.approval_status == "pending"
    assert shipment.planning_run_id.startswith("REDIST-")
    assert "AUTHS_REDISTRIBUTION" in shipment.approval_notes

    # Verify audit movement was logged
    mov = db_session.query(StockMovement).filter(StockMovement.shipment_id == shipment.shipment_id).first()
    assert mov is not None
    assert mov.movement_type == "proposed_dispatch"


def test_cross_organization_redistribution_strictly_forbidden(db_session: Session, setup_redistribution_network):
    """An organization cannot recommend or propose redistribution of competitor stock."""
    user_b = AuthenticatedUser(user_id="USER-B", role="planner", org_id="ORG-REDIST-B")

    # Org B user cannot propose redistribution from Org A's Mumbai facility
    payload = CreateRedistributionProposalRequest(
        sku_id="SKU-CHOC-01",
        source_location_id="LOC-WH-MUMBAI",
        destination_location_id="LOC-DC-PUNE",
        quantity=50.0,
    )

    with pytest.raises(Exception) as excinfo:
        create_redistribution_shipment_proposal(db_session, user_b, payload)
    assert "404" in str(excinfo.value)


# =============================================================================
# 3. HTTP API ENDPOINT TESTS
# =============================================================================

def test_api_redistribution_recommendations_endpoint(client: TestClient, db_session: Session, setup_redistribution_network, monkeypatch):
    """GET /api/redistribution/recommendations enforces tenant isolation and returns candidate rankings."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)

    headers = auth_headers("USER-A", "planner", "ORG-REDIST-A")
    res = client.get("/api/redistribution/recommendations", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["recommendations_count"] >= 1
    rec = data["recommendations"][0]
    assert rec["owner_org_id"] == "ORG-REDIST-A"
    assert rec["source_location_id"] == "LOC-WH-MUMBAI"
    assert rec["destination_location_id"] == "LOC-DC-PUNE"
    assert rec["recommended_quantity"] == 100.0


def test_api_submit_redistribution_proposal_endpoint(client: TestClient, db_session: Session, setup_redistribution_network, monkeypatch):
    """POST /api/redistribution/propose creates a formal proposal integrated with shipments."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)

    headers = auth_headers("USER-A", "planner", "ORG-REDIST-A")
    payload = {
        "sku_id": "SKU-CHOC-01",
        "source_location_id": "LOC-WH-MUMBAI",
        "destination_location_id": "LOC-DC-PUNE",
        "quantity": 50.0,
        "batch_number": "BATCH-MUM-25D",
        "notes": "Prevent 50 cases chocolate expiry",
    }
    res = client.post("/api/redistribution/propose", headers=headers, json=payload)

    assert res.status_code == 201
    shipment_data = res.json()
    assert shipment_data["shipment_id"].startswith("SHP-")
    assert shipment_data["status"] == "proposed"
    assert shipment_data["approval_status"] == "pending"
    assert shipment_data["quantity"] == 50.0
