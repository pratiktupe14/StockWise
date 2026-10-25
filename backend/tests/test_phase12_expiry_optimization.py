from datetime import date, timedelta, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.entities import (
    Organization,
    Location,
    Product,
    Route,
    InventorySnapshot,
    SalesHistory,
)
from app.services.optimizer_service import run_distribution_optimization
from app.schemas.planning import OptimizationRequest


def _setup_expiry_network(client: TestClient, db_session: Session):
    """
    Sets up a clean multi-tier distribution network:
    - FMCG Company Org: ORG-FMCG
    - Retail Partner Org: ORG-RET
    - Central Plant (Source 1): LOC-PLANT-BLR
    - Regional DC (Source 2): LOC-RDC-HYD
    - Destination Store (Retail): LOC-STORE-CHN
    - Product: SKU-MILK-1L (shelf_life_days=90)
    - Routes:
      - BLR -> CHN: lead_time = 2 days, cost = 3.0
      - HYD -> CHN: lead_time = 4 days, cost = 5.0
    """
    # Orgs
    client.post("/api/organizations", json={"org_id": "ORG-FMCG", "name": "FMCG India", "org_type": "fmcg_company"})
    client.post("/api/organizations", json={"org_id": "ORG-RET", "name": "Metro Retailers", "org_type": "retailer"})

    # Locations
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-PLANT-BLR",
            "name": "Bangalore Central Plant",
            "location_type": "manufacturing_plant",
            "region": "South",
            "city": "Bangalore",
            "owner_org_id": "ORG-FMCG",
            "is_active": True,
        },
    )
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-RDC-HYD",
            "name": "Hyderabad Regional DC",
            "location_type": "regional_warehouse",
            "region": "South",
            "city": "Hyderabad",
            "owner_org_id": "ORG-FMCG",
            "is_active": True,
        },
    )
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-STORE-CHN",
            "name": "Chennai Hypermarket",
            "location_type": "retail_destination",
            "region": "South",
            "city": "Chennai",
            "owner_org_id": "ORG-RET",
            "is_active": True,
        },
    )

    # Product
    db_session.add(
        Product(
            sku_id="SKU-MILK-1L",
            name="Farm Fresh UHT Milk 1L",
            category="Dairy",
            unit="cases",
            case_pack=12,
            shelf_life_days=90,
        )
    )

    # Routes
    db_session.add(
        Route(
            from_location_id="LOC-PLANT-BLR",
            to_location_id="LOC-STORE-CHN",
            lead_time_days=2.0,
            cost_rate=3.0,
            is_active=True,
        )
    )
    db_session.add(
        Route(
            from_location_id="LOC-RDC-HYD",
            to_location_id="LOC-STORE-CHN",
            lead_time_days=4.0,
            cost_rate=5.0,
            is_active=True,
        )
    )
    db_session.commit()

    # Seed sales history at destination to establish 100 units demand gap
    # 20 units/day for 7 days = 140 units forecast, 40 on-hand = 100 gap
    today = datetime.now(timezone.utc).date()
    for d in range(14):
        db_session.add(
            SalesHistory(
                sku_id="SKU-MILK-1L",
                destination_id="LOC-STORE-CHN",
                sales_date=today - timedelta(days=15 - d),
                quantity=20.0,
            )
        )
    # Store currently has 40 units
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-DEST",
            sku_id="SKU-MILK-1L",
            location_id="LOC-STORE-CHN",
            on_hand=40.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            as_of_date=today,
            owner_org_id="ORG-RET",
        )
    )
    db_session.commit()


# =============================================================================
# 1. EXPIRED STOCK EXCLUSION TEST
# =============================================================================

def test_expired_stock_excluded_from_optimization(client: TestClient, db_session: Session):
    """
    Source facility has 200 units on-hand, but expiry date was yesterday.
    Optimizer must strictly exclude it and produce an explicit unmet demand receipt.
    """
    _setup_expiry_network(client, db_session)
    today = datetime.now(timezone.utc).date()

    # Source has 200 units, expired yesterday
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-SRC-EXP",
            sku_id="SKU-MILK-1L",
            location_id="LOC-PLANT-BLR",
            on_hand=200.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            batch_number="BATCH-EXPIRED",
            expiry_date=today - timedelta(days=1),
            as_of_date=today,
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    req = OptimizationRequest(horizon_days=7, objective_strategy="service-first")
    plan = run_distribution_optimization(db_session, req)

    # Must allocate 0 units from expired stock
    assert plan.fulfilled_demand_units == 0.0
    assert len(plan.recommended_shipments) == 0
    assert plan.unmet_demand_units > 0.0

    # Decision receipt / unmet breakdown explains why
    assert len(plan.unmet_demand_breakdown) == 1
    reasons = plan.unmet_demand_breakdown[0]["reasons"]
    assert any("expired" in r.lower() for r in reasons)


# =============================================================================
# 2. NEAR-EXPIRY STOCK EXCLUDED WHEN FAILING DESTINATION SHELF LIFE
# =============================================================================

def test_near_expiry_excluded_for_destination_shelf_life(client: TestClient, db_session: Session):
    """
    Destination requires 15 days minimum shelf life.
    BLR -> CHN lead time is 2 days.
    Batch expires in 10 days. Shelf life upon arrival = 10 - 2 = 8 days < 15 days required.
    Optimizer must reject this near-expiry stock and explain the violation.
    """
    _setup_expiry_network(client, db_session)
    today = datetime.now(timezone.utc).date()

    # Stock expires in 10 days
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-SRC-NEAR",
            sku_id="SKU-MILK-1L",
            location_id="LOC-PLANT-BLR",
            on_hand=200.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            batch_number="BATCH-NEAR-EXPIRY",
            expiry_date=today + timedelta(days=10),
            as_of_date=today,
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    # Request requiring 15 days minimum shelf life at destination receipt
    req = OptimizationRequest(
        horizon_days=7,
        objective_strategy="service-first",
        min_remaining_shelf_life_days=15,
    )
    plan = run_distribution_optimization(db_session, req)

    # Ineligible because 8d arrival shelf life < 15d required
    assert plan.fulfilled_demand_units == 0.0
    assert len(plan.recommended_shipments) == 0

    # Verify explicit rejection in unmet demand breakdown
    assert len(plan.unmet_demand_breakdown) == 1
    reasons = plan.unmet_demand_breakdown[0]["reasons"]
    assert any("insufficient shelf life" in r.lower() for r in reasons)


# =============================================================================
# 3. ELIGIBLE STOCK SELECTED AND FULFILLED CORRECTLY
# =============================================================================

def test_eligible_stock_selected_and_fulfilled(client: TestClient, db_session: Session):
    """
    Source has 200 units with 60 days remaining shelf life.
    Destination needs 100 units and requires 15 days shelf life.
    Lead time is 2 days -> arrival shelf life is 58 days >= 15.
    Optimizer must allocate 100 units from this eligible source.
    """
    _setup_expiry_network(client, db_session)
    today = datetime.now(timezone.utc).date()

    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-SRC-FRESH",
            sku_id="SKU-MILK-1L",
            location_id="LOC-PLANT-BLR",
            on_hand=200.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            batch_number="BATCH-FRESH-60D",
            expiry_date=today + timedelta(days=60),
            as_of_date=today,
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    req = OptimizationRequest(
        horizon_days=7,
        objective_strategy="service-first",
        min_remaining_shelf_life_days=15,
    )
    plan = run_distribution_optimization(db_session, req)

    assert plan.fulfilled_demand_units == 100.0
    assert len(plan.recommended_shipments) == 1
    shp = plan.recommended_shipments[0]
    assert shp.source_location_id == "LOC-PLANT-BLR"
    assert shp.quantity == 100.0
    assert len(plan.decision_receipts) == 1


# =============================================================================
# 4. RESERVED AND BLOCKED QUANTITIES RESPECTED
# =============================================================================

def test_reserved_and_blocked_quantities_subtracted(client: TestClient, db_session: Session):
    """
    Source has 150 on-hand, but 50 reserved and 30 blocked -> 70 dispatchable.
    Stock has 45 days shelf life (eligible).
    Demand is 100 units.
    Optimizer can only allocate at most 70 units from this source.
    """
    _setup_expiry_network(client, db_session)
    today = datetime.now(timezone.utc).date()

    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-SRC-PARTIAL",
            sku_id="SKU-MILK-1L",
            location_id="LOC-PLANT-BLR",
            on_hand=150.0,
            reserved=50.0,
            blocked=30.0,
            confirmed_incoming=0.0,
            batch_number="BATCH-PARTIAL",
            expiry_date=today + timedelta(days=45),
            as_of_date=today,
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    req = OptimizationRequest(
        horizon_days=7,
        objective_strategy="service-first",
        min_remaining_shelf_life_days=10,
    )
    plan = run_distribution_optimization(db_session, req)

    # Exactly 70 units can be allocated, leaving 30 unmet demand
    assert plan.fulfilled_demand_units == 70.0
    assert plan.unmet_demand_units == 30.0
    assert len(plan.recommended_shipments) == 1
    assert plan.recommended_shipments[0].quantity == 70.0


# =============================================================================
# 5. MISSING EXPIRY DATA HANDLED UNDER CONSERVATIVE POLICY
# =============================================================================

def test_missing_expiry_data_handled_conservatively(client: TestClient, db_session: Session):
    """
    When destination requires shelf life verification or strict batch expiry is requested,
    unverified stock without an expiry date cannot be certified and is conservatively excluded.
    """
    _setup_expiry_network(client, db_session)
    today = datetime.now(timezone.utc).date()

    # Stock has no expiry date
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-SRC-NOEXP",
            sku_id="SKU-MILK-1L",
            location_id="LOC-PLANT-BLR",
            on_hand=200.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            batch_number="BATCH-NO-DATE",
            expiry_date=None,
            as_of_date=today,
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    # Strict batch expiry requested
    req = OptimizationRequest(
        horizon_days=7,
        objective_strategy="service-first",
        require_batch_expiry=True,
    )
    plan = run_distribution_optimization(db_session, req)

    assert plan.fulfilled_demand_units == 0.0
    assert len(plan.recommended_shipments) == 0
    assert len(plan.unmet_demand_breakdown) == 1
    reasons = plan.unmet_demand_breakdown[0]["reasons"]
    assert any("unknown expiry date" in r.lower() or "missing" in r.lower() for r in reasons)


# =============================================================================
# 6. ARRIVAL DATE AND TRANSIT TIME CALCULATION
# =============================================================================

def test_arrival_date_transit_time_distinguishes_sources(client: TestClient, db_session: Session):
    """
    Batch expires in 5 days.
    Route 1 (BLR -> CHN): lead time 2 days -> arrival in 2 days -> 3 days remaining >= 2.
    Route 2 (HYD -> CHN): lead time 4 days -> arrival in 4 days -> 1 day remaining < 2.
    If destination requires 2 days shelf life at arrival:
    BLR is eligible (3d >= 2d), HYD is ineligible (1d < 2d).
    """
    _setup_expiry_network(client, db_session)
    today = datetime.now(timezone.utc).date()

    # Put the same 5-day batch at HYD (lead time 4d)
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-HYD-5D",
            sku_id="SKU-MILK-1L",
            location_id="LOC-RDC-HYD",
            on_hand=150.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            batch_number="BATCH-5D",
            expiry_date=today + timedelta(days=5),
            as_of_date=today,
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    req = OptimizationRequest(
        horizon_days=7,
        objective_strategy="service-first",
        min_remaining_shelf_life_days=2,
    )
    plan = run_distribution_optimization(db_session, req)

    # HYD has lead time 4d, arrival shelf life 1d < 2d required -> excluded!
    assert plan.fulfilled_demand_units == 0.0
    assert any("insufficient shelf life" in r.lower() for r in plan.unmet_demand_breakdown[0]["reasons"])


# =============================================================================
# 7. INFEASIBLE RECOMMENDATIONS PRODUCE EXPLICIT REASONS IN RECEIPTS
# =============================================================================

def test_infeasible_recommendations_produce_explicit_reasons_in_receipts(client: TestClient, db_session: Session):
    """
    Multiple candidate sources rejected for distinct reasons:
    - BLR rejected due to expired stock.
    - HYD rejected due to insufficient arrival shelf life.
    Decision Receipt / unmet breakdown must record clear, specific reasons for each rejected candidate.
    """
    _setup_expiry_network(client, db_session)
    today = datetime.now(timezone.utc).date()

    # BLR has expired stock
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-BLR-EXP",
            sku_id="SKU-MILK-1L",
            location_id="LOC-PLANT-BLR",
            on_hand=100.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            batch_number="B-EXP",
            expiry_date=today - timedelta(days=3),
            as_of_date=today,
            owner_org_id="ORG-FMCG",
        )
    )
    # HYD has near-expiry stock (expires in 6 days, lead time 4 days -> 2 days arrival < 10 days required)
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-HYD-NEAR",
            sku_id="SKU-MILK-1L",
            location_id="LOC-RDC-HYD",
            on_hand=100.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            batch_number="B-NEAR",
            expiry_date=today + timedelta(days=6),
            as_of_date=today,
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    req = OptimizationRequest(
        horizon_days=7,
        objective_strategy="service-first",
        min_remaining_shelf_life_days=10,
    )
    plan = run_distribution_optimization(db_session, req)

    assert plan.fulfilled_demand_units == 0.0
    assert len(plan.unmet_demand_breakdown) == 1
    reasons = plan.unmet_demand_breakdown[0]["reasons"]
    # Check that both locations have explicit failure reasons recorded
    assert any("Bangalore Central Plant" in r and "expired" in r for r in reasons)
    assert any("Hyderabad Regional DC" in r and "insufficient shelf life" in r for r in reasons)
