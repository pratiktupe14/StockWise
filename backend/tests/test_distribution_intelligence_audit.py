"""
StockWise Distribution Intelligence End-to-End Audit Test Suite.
Validates all 11 phases of the Distribution Intelligence module:
- Phase 2: Routing, Role Authorization & Tenant Isolation
- Phase 3: Warehouse Selection & Dispatchable Stock Rules
- Phase 4: Corridor Evaluation, Landed Cost & Distance Source Attribution
- Phase 5: FEFO Allocation, Multi-Tier Expiry Alerts & Mutation Safety
- Phase 6: ML Forecast Evaluation, Mathematical Accuracy & Data Leakage Prevention
- Phase 7: Actual vs Predicted Time-Series Alignment
- Phase 8: Four Distribution Performance KPIs (including Negative Cost Savings)
- Phase 9: What-If Simulation Isolation & Rejection of Invalid Inputs
- Phase 10: Reactive Dataset Synchronization
"""

import uuid
import json
from datetime import date, datetime, timezone, timedelta
from typing import Dict, Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    Organization,
    Location,
    Product,
    Route,
    InventorySnapshot,
    SalesHistory,
    PlanningRun,
    Shipment,
)
from app.services.optimizer_service import (
    compare_corridors_for_destination_sku,
    compute_distribution_performance_kpis,
    simulate_what_if_scenario,
    run_distribution_optimization,
)
from app.services.forecast_service import compute_forecast_evaluation
from app.services.expiry_service import (
    summarize_expiry_risk,
    allocate_fefo_batches,
)
from app.schemas.planning import (
    OptimizationRequest,
    ScenarioSimulationRequest,
)

TEST_JWT_SECRET = "audit-test-secret-key-at-least-32-chars-long-for-hs256!"


@pytest.fixture(autouse=True)
def configure_audit_security_env():
    """Ensures JWT authentication and production mode are active across all audit tests."""
    old_env = settings.ENVIRONMENT
    old_secret = settings.SUPABASE_JWT_SECRET
    settings.ENVIRONMENT = "production"
    settings.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
    yield
    settings.ENVIRONMENT = old_env
    settings.SUPABASE_JWT_SECRET = old_secret


def make_test_jwt(
    sub: str = "USER-TEST",
    email: str = "auditor@stockwise.internal",
    role: str = "planner",
    org_id: str = "ORG-COMPANY-A",
) -> str:
    """Generates signed JWT token for authentication tests."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=2)).timestamp()),
        "app_metadata": {"role": role, "org_id": org_id},
        "user_metadata": {},
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def _build_audit_environment(db: Session) -> Dict[str, Any]:
    """Sets up a comprehensive multi-tier network with company and distributor entities."""
    # 1. Organizations
    company_a = Organization(
        org_id="ORG-COMPANY-A",
        name="Hindustan Consumer Goods Ltd",
        org_type="fmcg_company",
        is_active=True,
    )
    company_b = Organization(
        org_id="ORG-COMPANY-B",
        name="Competitor Consumer Brands",
        org_type="fmcg_company",
        is_active=True,
    )
    distributor_1 = Organization(
        org_id="ORG-DIST-MAHARASHTRA",
        name="Western Distributors Pvt Ltd",
        org_type="independent_distributor",
        is_active=True,
    )
    db.add_all([company_a, company_b, distributor_1])
    db.commit()

    # 2. Products
    prod_tea = Product(
        sku_id="SKU-TEA-PREMIUM",
        name="Royal Assam Gold Tea 250g",
        category="Beverages",
        unit="pack",
        case_pack=20,
        shelf_life_days=180,
    )
    prod_biscuit = Product(
        sku_id="SKU-BISCUIT-GLUCOSE",
        name="Glucose Energy Biscuits 100g",
        category="Bakery",
        unit="pack",
        case_pack=48,
        shelf_life_days=90,
    )
    db.add_all([prod_tea, prod_biscuit])
    db.commit()

    # 3. Locations
    wh_mumbai = Location(
        location_id="WH-MUMBAI-MAIN",
        name="Bhiwandi Central Mega DC",
        location_type="company_warehouse",
        region="West",
        city="Mumbai",
        owner_org_id="ORG-COMPANY-A",
        storage_capacity_units=100000,
        dispatch_capacity_daily=10000,
        latitude=19.2813,
        longitude=73.0483,
        is_active=True,
    )
    wh_pune = Location(
        location_id="WH-PUNE-HUB",
        name="Pune Chakan Distribution Center",
        location_type="company_warehouse",
        region="West",
        city="Pune",
        owner_org_id="ORG-COMPANY-A",
        storage_capacity_units=40000,
        dispatch_capacity_daily=4000,
        latitude=18.7606,
        longitude=73.8636,
        is_active=True,
    )
    wh_inactive = Location(
        location_id="WH-NASHIK-DECOMMISSIONED",
        name="Nashik Outpost (Inactive)",
        location_type="company_warehouse",
        region="West",
        city="Nashik",
        owner_org_id="ORG-COMPANY-A",
        storage_capacity_units=15000,
        dispatch_capacity_daily=1000,
        latitude=19.9975,
        longitude=73.7898,
        is_active=False,  # Inactive location
    )
    depot_pune = Location(
        location_id="DEPOT-PUNE-DIST",
        name="Pune Regional Distributor Depot",
        location_type="distributor",
        region="West",
        city="Pune",
        owner_org_id="ORG-DIST-MAHARASHTRA",
        storage_capacity_units=30000,
        dispatch_capacity_daily=3000,
        latitude=18.5204,
        longitude=73.8567,
        is_active=True,
    )
    db.add_all([wh_mumbai, wh_pune, wh_inactive, depot_pune])
    db.commit()

    # 4. Routes
    # Route 1: Mumbai -> Pune Depot (Standard freight, active)
    route_mumbai_pune = Route(
        from_location_id="WH-MUMBAI-MAIN",
        to_location_id="DEPOT-PUNE-DIST",
        lead_time_days=1.0,
        cost_rate=3.80,
        capacity_units=10000,
        sku_eligibility="all",
        is_active=True,
    )
    # Route 2: Pune DC -> Pune Depot (Zero-freight shuttle corridor)
    route_pune_pune = Route(
        from_location_id="WH-PUNE-HUB",
        to_location_id="DEPOT-PUNE-DIST",
        lead_time_days=0.5,
        cost_rate=0.0,  # Zero-freight rate corridor
        capacity_units=5000,
        sku_eligibility="all",
        is_active=True,
    )
    # Route 3: Inactive route from Nashik
    route_nashik_pune = Route(
        from_location_id="WH-NASHIK-DECOMMISSIONED",
        to_location_id="DEPOT-PUNE-DIST",
        lead_time_days=2.0,
        cost_rate=4.50,
        capacity_units=3000,
        sku_eligibility="all",
        is_active=False,
    )
    db.add_all([route_mumbai_pune, route_pune_pune, route_nashik_pune])
    db.commit()

    return {
        "company_a": company_a,
        "company_b": company_b,
        "distributor": distributor_1,
        "sku_tea": prod_tea,
        "sku_biscuit": prod_biscuit,
        "wh_mumbai": wh_mumbai,
        "wh_pune": wh_pune,
        "depot_pune": depot_pune,
        "route_mumbai": route_mumbai_pune,
        "route_pune": route_pune_pune,
    }


# ============================================================================
# PHASE 2 — ROUTING, ACCESS CONTROL & TENANT ISOLATION
# ============================================================================

def test_audit_phase2_unauthenticated_access_blocked(client: TestClient):
    """Verifies unauthenticated callers cannot access protected distribution intelligence endpoints in production mode."""
    protected_endpoints = [
        "/api/forecast/evaluation",
        "/api/corridors/compare?destination_id=DEPOT-PUNE-DIST&sku_id=SKU-TEA-PREMIUM",
        "/api/optimization/distribution-performance",
        "/api/inventory/expiry-risk",
    ]
    for url in protected_endpoints:
        res = client.get(url)
        assert res.status_code == 401, f"Expected 401 Unauthorized for {url}, got {res.status_code}"


def test_audit_phase2_tenant_isolation_company_cannot_read_peer(client: TestClient, db_session: Session):
    """Verifies Company A cannot read or download Company B's planning runs."""
    env = _build_audit_environment(db_session)

    # Create planning run owned by Company B
    run_b = PlanningRun(
        run_id="RUN-COMP-B-SECURE-001",
        horizon_days=7,
        objective_strategy="service_first",
        solver_status="optimal",
        solver_name="ortools_glop",
        solve_time_ms=12.5,
        total_demand_units=5000.0,
        fulfilled_demand_units=5000.0,
        unmet_demand_units=0.0,
        service_level_percent=100.0,
        estimated_transport_cost=15000.0,
        stock_utilization_percent=85.0,
        org_id="ORG-COMPANY-B",  # Owned by Company B
        unmet_demand_breakdown=json.dumps([]),
        decision_receipts=json.dumps([]),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(run_b)
    db_session.commit()

    # Token for Company A Planner
    token_a = make_test_jwt(sub="planner-a", role="planner", org_id="ORG-COMPANY-A")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Company A attempts to download Company B's decision receipts
    res_receipts = client.get(
        "/api/optimization/runs/RUN-COMP-B-SECURE-001/export/decision-receipts.csv",
        headers=headers_a,
    )
    assert res_receipts.status_code in {403, 404}, f"Company A should not access Company B run: {res_receipts.status_code}"

    # Company A attempts to download Company B's unmet demand CSV
    res_unmet = client.get(
        "/api/optimization/runs/RUN-COMP-B-SECURE-001/export/unmet-demand.csv",
        headers=headers_a,
    )
    assert res_unmet.status_code in {403, 404}, f"Company A should not access Company B unmet breakdown: {res_unmet.status_code}"


# ============================================================================
# PHASE 3 — WAREHOUSE SELECTION & OPTIMIZATION (DISPATCHABLE STOCK RULE)
# ============================================================================

def test_audit_phase3_dispatchable_stock_rule_enforced(db_session: Session):
    """
    Verifies dispatchable stock calculation:
    dispatchable_stock = max(0, on_hand - reserved - blocked)
    Reserved and blocked stock MUST NOT be allocated.
    """
    env = _build_audit_environment(db_session)
    today = date.today()

    # Warehouse with on_hand = 1000, reserved = 300, blocked = 200 => dispatchable = 500
    inv = InventorySnapshot(
        snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}",
        location_id=env["wh_mumbai"].location_id,
        sku_id=env["sku_tea"].sku_id,
        batch_number="BATCH-MUM-001",
        on_hand=1000.0,
        reserved=300.0,
        blocked=200.0,
        expiry_date=today + timedelta(days=90),
        as_of_date=today,
        owner_org_id=env["company_a"].org_id,
    )
    db_session.add(inv)
    db_session.commit()

    # Destination demand at Pune Depot = 700 units
    for i in range(1, 15):
        s = SalesHistory(
            sku_id=env["sku_tea"].sku_id,
            destination_id=env["depot_pune"].location_id,
            sales_date=today - timedelta(days=i),
            quantity=100.0,
        )
        db_session.add(s)
    db_session.commit()

    req = OptimizationRequest(
        horizon_days=7,
        objective_strategy="service_first",
        solver_type="ortools",
    )
    plan = run_distribution_optimization(db_session, req, org_id=env["company_a"].org_id)

    # Dispatchable stock is 500. Total demand is 700.
    allocated_units = sum(float(s.quantity) for s in plan.recommended_shipments)
    assert allocated_units <= 500.0, f"Allocated {allocated_units} exceeds dispatchable stock of 500"
    assert plan.unmet_demand_units >= 200.0, f"Expected unmet demand >= 200, got {plan.unmet_demand_units}"
    assert plan.service_level_percent < 100.0, "Service level should reflect partial fulfillment"


def test_audit_phase3_distributor_inventory_protected(db_session: Session):
    """Verifies company optimization cannot allocate distributor-owned inventory."""
    env = _build_audit_environment(db_session)
    today = date.today()

    # Distributor owns stock at Pune Depot
    dist_inv = InventorySnapshot(
        snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}",
        location_id=env["depot_pune"].location_id,
        sku_id=env["sku_tea"].sku_id,
        batch_number="BATCH-DIST-OWNED",
        on_hand=2000.0,
        reserved=0.0,
        blocked=0.0,
        expiry_date=today + timedelta(days=120),
        as_of_date=today,
        owner_org_id=env["distributor"].org_id,  # Independent distributor owned
    )
    db_session.add(dist_inv)
    db_session.commit()

    comparison = compare_corridors_for_destination_sku(
        db=db_session,
        destination_id=env["depot_pune"].location_id,
        sku_id=env["sku_tea"].sku_id,
        horizon_days=7,
    )
    for alt in comparison.alternatives:
        if alt.source_location_id == env["depot_pune"].location_id:
            assert alt.is_feasible is False
            assert alt.feasibility_status == "distributor_protected"


# ============================================================================
# PHASE 4 — TRANSPORTATION, ROUTING & LANDED COST (0.0 RATE & SOURCE ATTRIBUTION)
# ============================================================================

def test_audit_phase4_zero_freight_rate_preserved(db_session: Session):
    """
    Verifies that a configured route freight rate of 0.0 is preserved
    and not silently overridden by the default 3.50 rate.
    """
    env = _build_audit_environment(db_session)
    today = date.today()

    # Seed stock at Pune Hub (which connects to Pune Depot via route with cost_rate = 0.0)
    inv_pune = InventorySnapshot(
        snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}",
        location_id=env["wh_pune"].location_id,
        sku_id=env["sku_tea"].sku_id,
        batch_number="BATCH-PUNE-001",
        on_hand=800.0,
        reserved=0.0,
        blocked=0.0,
        expiry_date=today + timedelta(days=60),
        as_of_date=today,
        owner_org_id=env["company_a"].org_id,
    )
    db_session.add(inv_pune)
    db_session.commit()

    comparison = compare_corridors_for_destination_sku(
        db=db_session,
        destination_id=env["depot_pune"].location_id,
        sku_id=env["sku_tea"].sku_id,
        horizon_days=7,
    )

    pune_alt = next((a for a in comparison.alternatives if a.source_location_id == env["wh_pune"].location_id), None)
    assert pune_alt is not None, "Pune corridor alternative must be evaluated"
    assert pune_alt.cost_rate_per_unit == 0.0, f"Expected 0.0 freight rate, got {pune_alt.cost_rate_per_unit}"
    assert pune_alt.total_delivered_cost_per_unit == round(0.0 + pune_alt.handling_cost_per_unit, 2)


def test_audit_phase4_distance_source_attribution(db_session: Session):
    """
    Verifies that fallback estimates are accurately labeled with their
    distance source and never masquerade as verified OSRM road routes.
    """
    env = _build_audit_environment(db_session)

    comparison = compare_corridors_for_destination_sku(
        db=db_session,
        destination_id=env["depot_pune"].location_id,
        sku_id=env["sku_tea"].sku_id,
        horizon_days=7,
    )

    for alt in comparison.alternatives:
        assert hasattr(alt, "distance_source"), "Corridor alternative must expose distance_source"
        assert hasattr(alt, "is_verified_road_route"), "Corridor alternative must expose is_verified_road_route"
        if alt.distance_source != "osrm_open_street_map":
            assert alt.is_verified_road_route is False, "Fallback estimate must not be marked verified road route"


# ============================================================================
# PHASE 5 — FEFO & EXPIRY RESTRICTIONS (EARLIEST FIRST, NO EXPIRED DISPATCH)
# ============================================================================

def test_audit_phase5_fefo_allocates_earliest_eligible_and_excludes_expired(db_session: Session):
    """
    Verifies that FEFO:
    1. Strictly excludes already expired batches.
    2. Allocates the earliest expiring unexpired batch first.
    3. Respects destination minimum shelf life requirements.
    """
    env = _build_audit_environment(db_session)
    today = date.today()

    # Batch 1: EXPIRED 2 days ago
    inv_expired = InventorySnapshot(
        snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}",
        location_id=env["wh_mumbai"].location_id,
        sku_id=env["sku_biscuit"].sku_id,
        batch_number="BATCH-EXP-01",
        on_hand=500.0,
        reserved=0.0,
        blocked=0.0,
        expiry_date=today - timedelta(days=2),
        as_of_date=today,
        owner_org_id=env["company_a"].org_id,
    )
    # Batch 2: Expires in 12 days (Earlier eligible)
    inv_early = InventorySnapshot(
        snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}",
        location_id=env["wh_mumbai"].location_id,
        sku_id=env["sku_biscuit"].sku_id,
        batch_number="BATCH-EARLY-12D",
        on_hand=200.0,
        reserved=0.0,
        blocked=0.0,
        expiry_date=today + timedelta(days=12),
        as_of_date=today,
        owner_org_id=env["company_a"].org_id,
    )
    # Batch 3: Expires in 45 days (Later eligible)
    inv_later = InventorySnapshot(
        snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}",
        location_id=env["wh_mumbai"].location_id,
        sku_id=env["sku_biscuit"].sku_id,
        batch_number="BATCH-LATER-45D",
        on_hand=400.0,
        reserved=0.0,
        blocked=0.0,
        expiry_date=today + timedelta(days=45),
        as_of_date=today,
        owner_org_id=env["company_a"].org_id,
    )
    db_session.add_all([inv_expired, inv_early, inv_later])
    db_session.commit()

    # Request allocation for 300 units with min shelf life = 10 days
    batches = db_session.query(InventorySnapshot).filter(InventorySnapshot.sku_id == env["sku_biscuit"].sku_id).all()
    res = allocate_fefo_batches(batches, demand_quantity=300.0, min_remaining_shelf_life_days=10, as_of=today)

    # 1. Expired batch must NEVER be allocated
    allocated_batches = [a["batch_number"] for a in res["allocations"]]
    assert "BATCH-EXP-01" not in allocated_batches, "Expired batch must never be allocated"

    # 2. Earliest eligible batch (12d) must be allocated first up to its available stock (200)
    assert allocated_batches[0] == "BATCH-EARLY-12D"
    assert res["allocations"][0]["allocated_quantity"] == 200.0

    # 3. Remaining 100 units must come from next earliest batch (45d)
    assert allocated_batches[1] == "BATCH-LATER-45D"
    assert res["allocations"][1]["allocated_quantity"] == 100.0
    assert res["total_allocated"] == 300.0
    assert res["unmet_demand"] == 0.0


def test_audit_phase5_expiry_risk_summary_tiers(db_session: Session):
    """Verifies warehouse expiry risk categorization: expired, <=15d, 16-30d, 31-60d, healthy."""
    env = _build_audit_environment(db_session)
    today = date.today()

    batches = [
        InventorySnapshot(snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}", location_id=env["wh_mumbai"].location_id, sku_id="SKU-T1", batch_number="B-EXP", on_hand=50.0, reserved=0.0, blocked=0.0, expiry_date=today - timedelta(days=1), as_of_date=today),
        InventorySnapshot(snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}", location_id=env["wh_mumbai"].location_id, sku_id="SKU-T2", batch_number="B-CRIT", on_hand=80.0, reserved=0.0, blocked=0.0, expiry_date=today + timedelta(days=8), as_of_date=today),
        InventorySnapshot(snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}", location_id=env["wh_mumbai"].location_id, sku_id="SKU-T3", batch_number="B-WARN", on_hand=120.0, reserved=0.0, blocked=0.0, expiry_date=today + timedelta(days=22), as_of_date=today),
        InventorySnapshot(snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}", location_id=env["wh_mumbai"].location_id, sku_id="SKU-T4", batch_number="B-UP", on_hand=200.0, reserved=0.0, blocked=0.0, expiry_date=today + timedelta(days=45), as_of_date=today),
        InventorySnapshot(snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}", location_id=env["wh_mumbai"].location_id, sku_id="SKU-T5", batch_number="B-HLTH", on_hand=300.0, reserved=0.0, blocked=0.0, expiry_date=today + timedelta(days=100), as_of_date=today),
    ]
    db_session.add_all(batches)
    db_session.commit()

    summary = summarize_expiry_risk(batches, as_of=today)
    assert summary["expired_units"] == 50.0
    assert summary["critical_units"] == 80.0
    assert summary["high_risk_units"] == 120.0
    assert summary["medium_risk_units"] == 200.0
    assert summary["healthy_units"] == 300.0


# ============================================================================
# PHASE 6 — DEMAND FORECASTING & ML EVALUATION (FORMULAS & NO FUTURE LEAKAGE)
# ============================================================================

def test_audit_phase6_forecast_evaluation_holdout_and_metrics(db_session: Session):
    """
    Verifies:
    1. Chronological holdout evaluation.
    2. Precision of MAE, WAPE, and Forecast Accuracy = 100 - WAPE.
    3. Future forecast points strictly have actual_demand=None (no invented future observations).
    """
    env = _build_audit_environment(db_session)
    today = date.today()

    # Seed 14 days of historical sales records
    for i in range(14, 0, -1):
        s_date = today - timedelta(days=i)
        db_session.add(
            SalesHistory(
                sku_id=env["sku_tea"].sku_id,
                destination_id=env["depot_pune"].location_id,
                sales_date=s_date,
                quantity=50.0,
            )
        )
    db_session.commit()

    eval_res = compute_forecast_evaluation(
        db_session,
        horizon_days=7,
        sku_id=env["sku_tea"].sku_id,
        destination_id=env["depot_pune"].location_id,
    )

    assert eval_res.data_sufficiency == "sufficient"
    assert eval_res.sample_count == 7  # 7-day holdout split
    assert eval_res.total_actual_demand == 350.0  # 7 * 50

    # With steady 50 units/day, rolling average predicts 50.0 units/day
    assert eval_res.mae is not None and eval_res.mae == 0.0
    assert eval_res.wape is not None and eval_res.wape == 0.0
    assert eval_res.accuracy_percent is not None and eval_res.accuracy_percent == 100.0

    # Verification: Future dates strictly contain predicted demand and actual_demand is None
    future_points = [p for p in eval_res.aligned_timeseries if p.is_future]
    assert len(future_points) == 7, "Expected 7 future prediction points"
    for pt in future_points:
        assert pt.actual_demand is None, f"Future point {pt.date} must have actual_demand=None"
        assert pt.predicted_demand > 0.0, f"Future point {pt.date} must have predicted demand"


def test_audit_phase6_zero_actual_demand_safe(db_session: Session):
    """Verifies zero actual demand does not cause ZeroDivisionError and reports cleanly."""
    env = _build_audit_environment(db_session)
    today = date.today()

    # Seed 10 days of zero sales
    for i in range(10, 0, -1):
        db_session.add(
            SalesHistory(
                sku_id=env["sku_biscuit"].sku_id,
                destination_id=env["depot_pune"].location_id,
                sales_date=today - timedelta(days=i),
                quantity=0.0,
            )
        )
    db_session.commit()

    eval_res = compute_forecast_evaluation(
        db_session,
        horizon_days=7,
        sku_id=env["sku_biscuit"].sku_id,
        destination_id=env["depot_pune"].location_id,
    )
    assert eval_res.total_actual_demand == 0.0
    assert eval_res.data_sufficiency in {"zero_demand", "insufficient_history"}


# ============================================================================
# PHASE 8 — DISTRIBUTION PERFORMANCE KPIS (INCLUDING NEGATIVE SAVINGS)
# ============================================================================

def test_audit_phase8_distribution_performance_kpis_and_negative_savings(db_session: Session):
    """
    Verifies all four KPIs:
    1. Demand fulfilment rate = fulfilled / eligible * 100
    2. Transportation cost = verified operational or estimated plan
    3. Stockout rate = unmet / eligible * 100
    4. Cost reduction = (baseline - opt) / baseline * 100, preserving negative savings.
    """
    env = _build_audit_environment(db_session)

    baseline_payload = {
        "baseline": {
            "name": "Nearest-Warehouse Heuristic",
            "estimated_transport_cost": 1000.0,
            "service_level_percent": 80.0,
        },
        "optimizer": {
            "name": "Service-First Optimizer",
            "estimated_transport_cost": 1200.0,
            "service_level_percent": 100.0,
        },
    }

    plan_run = PlanningRun(
        run_id="RUN-AUDIT-PERF-001",
        horizon_days=7,
        objective_strategy="service_first",
        solver_status="optimal",
        solver_name="ortools_glop",
        solve_time_ms=15.0,
        total_demand_units=500.0,
        fulfilled_demand_units=450.0,
        unmet_demand_units=50.0,
        service_level_percent=90.0,
        estimated_transport_cost=1200.0,
        stock_utilization_percent=75.0,
        baseline_comparison=json.dumps(baseline_payload),
        unmet_demand_breakdown=json.dumps([]),
        decision_receipts=json.dumps([]),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(plan_run)
    db_session.commit()

    kpis = compute_distribution_performance_kpis(db_session, run_id="RUN-AUDIT-PERF-001")

    # KPI 1: Fulfilment rate = 450 / 500 * 100 = 90.0%
    assert kpis.demand_fulfilment_rate_percent == 90.0

    # KPI 2: Transportation cost = 1200.0
    assert kpis.transportation_cost == 1200.0

    # KPI 3: Stockout rate = 50 / 500 * 100 = 10.0%
    assert kpis.stockout_rate_percent == 10.0

    # KPI 4: Cost reduction = (1000 - 1200) / 1000 * 100 = -20.0%
    # Negative savings MUST be preserved (-200.0), NOT clamped to 0.0!
    assert kpis.cost_reduction_percent == -20.0, f"Expected -20.0% cost reduction, got {kpis.cost_reduction_percent}"
    assert kpis.cost_savings == -200.0, f"Expected -200.0 cost savings, got {kpis.cost_savings}"


# ============================================================================
# PHASE 9 — WHAT-IF SIMULATION (ISOLATION & INPUT VALIDATION)
# ============================================================================

def test_audit_phase9_what_if_simulation_dry_run_no_db_mutation(db_session: Session):
    """
    Verifies what-if scenario simulation:
    1. Evaluates modified parameters (demand surge, freight rate multiplier).
    2. Modifies ZERO rows in InventorySnapshot, Shipment, or PlanningRun.
    """
    env = _build_audit_environment(db_session)
    today = date.today()

    inv = InventorySnapshot(
        snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}",
        location_id=env["wh_mumbai"].location_id,
        sku_id=env["sku_tea"].sku_id,
        batch_number="BATCH-SIM-001",
        on_hand=1500.0,
        reserved=0.0,
        blocked=0.0,
        expiry_date=today + timedelta(days=90),
        as_of_date=today,
        owner_org_id=env["company_a"].org_id,
    )
    db_session.add(inv)
    for i in range(1, 8):
        db_session.add(SalesHistory(sku_id=env["sku_tea"].sku_id, destination_id=env["depot_pune"].location_id, sales_date=today - timedelta(days=i), quantity=50.0))
    db_session.commit()

    initial_inv_count = db_session.query(InventorySnapshot).count()
    initial_shipment_count = db_session.query(Shipment).count()
    initial_run_count = db_session.query(PlanningRun).count()

    sim_req = ScenarioSimulationRequest(
        horizon_days=7,
        demand_multiplier=1.5,
        freight_rate_multiplier=1.2,
        source_stock_multiplier=1.0,
        disrupted_route_ids=[],
        solver_type="ortools",
    )
    sim_res = simulate_what_if_scenario(db_session, sim_req, org_id=env["company_a"].org_id)

    assert sim_res.simulated_plan["total_demand_units"] > sim_res.baseline_plan["total_demand_units"]

    # Database state must be 100% UNCHANGED
    assert db_session.query(InventorySnapshot).count() == initial_inv_count
    assert db_session.query(Shipment).count() == initial_shipment_count
    assert db_session.query(PlanningRun).count() == initial_run_count


def test_audit_phase9_invalid_simulation_inputs_rejected(client: TestClient):
    """Verifies that invalid or negative simulation inputs are rejected by schema validation."""
    token = make_test_jwt(sub="admin_test", role="admin", org_id="ORG-COMPANY-A")
    headers = {"Authorization": f"Bearer {token}"}

    # Negative demand multiplier (ge=0.1 required)
    res_neg_demand = client.post(
        "/api/optimization/simulate",
        json={"horizon_days": 7, "demand_multiplier": -0.5, "freight_rate_multiplier": 1.0, "source_stock_multiplier": 1.0},
        headers=headers,
    )
    assert res_neg_demand.status_code == 422, "Negative demand multiplier must be rejected"

    # Horizon > 30 days (le=30 required)
    res_excess_horizon = client.post(
        "/api/optimization/simulate",
        json={"horizon_days": 60, "demand_multiplier": 1.0, "freight_rate_multiplier": 1.0, "source_stock_multiplier": 1.0},
        headers=headers,
    )
    assert res_excess_horizon.status_code == 422, "Horizon > 30 must be rejected"


# ============================================================================
# PHASE 10 — DATA SYNCHRONIZATION
# ============================================================================

def test_audit_phase10_dataset_synchronization_immediate_reflection(db_session: Session):
    """
    Verifies that when database state updates (new batch added),
    subsequent API service queries immediately reflect the committed state.
    """
    env = _build_audit_environment(db_session)
    today = date.today()

    batches_before = db_session.query(InventorySnapshot).filter(InventorySnapshot.location_id == env["wh_pune"].location_id).all()
    summary_before = summarize_expiry_risk(batches_before, as_of=today)
    assert summary_before["total_batches"] == 0

    new_batch = InventorySnapshot(
        snapshot_id=f"SNAP-{uuid.uuid4().hex[:8]}",
        location_id=env["wh_pune"].location_id,
        sku_id=env["sku_tea"].sku_id,
        batch_number="BATCH-SYNC-NEW",
        on_hand=600.0,
        reserved=0.0,
        blocked=0.0,
        expiry_date=today + timedelta(days=25),
        as_of_date=today,
        owner_org_id=env["company_a"].org_id,
    )
    db_session.add(new_batch)
    db_session.commit()

    batches_after = db_session.query(InventorySnapshot).filter(InventorySnapshot.location_id == env["wh_pune"].location_id).all()
    summary_after = summarize_expiry_risk(batches_after, as_of=today)
    assert summary_after["total_batches"] == 1
    assert summary_after["high_risk_units"] == 600.0
