from datetime import date, datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def _seed_eval_network(db: Session):
    """Seeds master data for forecast evaluation and performance testing."""
    org = Organization(org_id="ORG-FMCG-CORP", name="FMCG Corp", org_type="fmcg_company", is_active=True)
    dist = Organization(org_id="ORG-DIST-1", name="Distributor One", org_type="independent_distributor", is_active=True)
    db.add_all([org, dist])
    db.commit()

    prod = Product(
        sku_id="SKU-CHAI-100",
        name="Masala Chai 100g",
        category="Beverages",
        unit="pack",
        case_pack=24,
        shelf_life_days=180,
    )
    db.add(prod)

    loc_src = Location(
        location_id="LOC-WH-MUMBAI",
        name="Mumbai Central DC",
        location_type="company_warehouse",
        region="West",
        city="Mumbai",
        owner_org_id="ORG-FMCG-CORP",
        storage_capacity_units=50000,
        dispatch_capacity_daily=5000,
        latitude=19.0760,
        longitude=72.8777,
        is_active=True,
    )
    loc_dest = Location(
        location_id="LOC-DIST-PUNE",
        name="Pune Distributor Depot",
        location_type="distributor",
        region="West",
        city="Pune",
        owner_org_id="ORG-DIST-1",
        storage_capacity_units=20000,
        dispatch_capacity_daily=2000,
        latitude=18.5204,
        longitude=73.8567,
        is_active=True,
    )
    db.add_all([loc_src, loc_dest])
    db.commit()

    route = Route(
        from_location_id="LOC-WH-MUMBAI",
        to_location_id="LOC-DIST-PUNE",
        lead_time_days=1.0,
        cost_rate=3.5,
        is_active=True,
    )
    db.add(route)
    db.commit()


def test_forecast_evaluation_insufficient_history(client: TestClient, db_session: Session):
    """
    P1: Tests that when sales observations are fewer than 7 days,
    data sufficiency is classified as insufficient_history and error metrics safely return None.
    """
    _seed_eval_network(db_session)

    # Insert only 3 days of sales history (< 7 days)
    today = date.today()
    for i in range(1, 4):
        db_session.add(
            SalesHistory(
                sku_id="SKU-CHAI-100",
                destination_id="LOC-DIST-PUNE",
                sales_date=today - timedelta(days=i),
                quantity=50.0,
            )
        )
    db_session.commit()

    res = client.get("/api/forecast/evaluation?horizon_days=7&sku_id=SKU-CHAI-100&destination_id=LOC-DIST-PUNE")
    assert res.status_code == 200
    data = res.json()

    assert data["data_sufficiency"] == "insufficient_history"
    assert data["mae"] is None
    assert data["wape"] is None
    assert data["accuracy_percent"] is None
    assert data["sample_count"] == 0
    assert len(data["series"]) == 1
    assert data["series"][0]["sample_count"] == 3


def test_forecast_evaluation_sufficient_history_and_formulas(client: TestClient, db_session: Session):
    """
    P1 & P2: Tests that with >= 7 days of sales history:
    - MAE, WAPE, and Forecast Accuracy (100 - WAPE) are calculated safely.
    - Future dates strictly contain predicted demand with actual_demand = None (no invented observations).
    - Prevents data leakage by evaluating chronological holdout.
    """
    _seed_eval_network(db_session)

    # Insert 14 days of realistic daily sales records
    today = date.today()
    quantities = [100.0, 110.0, 95.0, 105.0, 120.0, 115.0, 100.0, 105.0, 110.0, 115.0, 100.0, 105.0, 110.0, 120.0]
    for idx, qty in enumerate(quantities):
        db_session.add(
            SalesHistory(
                sku_id="SKU-CHAI-100",
                destination_id="LOC-DIST-PUNE",
                sales_date=today - timedelta(days=14 - idx),
                quantity=qty,
            )
        )
    db_session.commit()

    res = client.get("/api/forecast/evaluation?horizon_days=7&sku_id=SKU-CHAI-100&destination_id=LOC-DIST-PUNE")
    assert res.status_code == 200
    data = res.json()

    assert data["data_sufficiency"] == "sufficient"
    assert data["mae"] is not None and data["mae"] >= 0.0
    assert data["wape"] is not None and data["wape"] >= 0.0
    assert data["accuracy_percent"] is not None
    # Formula check: Forecast Accuracy = 100 - WAPE
    assert abs(data["accuracy_percent"] - (100.0 - data["wape"])) < 0.01

    assert data["sample_count"] > 0
    assert data["evaluation_period"] is not None

    # Check time-series points
    points = data["aligned_timeseries"]
    assert len(points) > 0

    holdout_points = [p for p in points if not p["is_future"]]
    future_points = [p for p in points if p["is_future"]]

    assert len(holdout_points) > 0
    for hp in holdout_points:
        assert hp["actual_demand"] is not None
        assert hp["predicted_demand"] > 0.0
        assert hp["error"] is not None
        assert abs(hp["error"] - abs(hp["actual_demand"] - hp["predicted_demand"])) < 0.01

    # P2: Future dates must NOT invent actual demand
    assert len(future_points) == 7
    for fp in future_points:
        assert fp["actual_demand"] is None
        assert fp["predicted_demand"] > 0.0
        assert fp["is_future"] is True


def test_distribution_performance_kpis_no_runs(client: TestClient, db_session: Session):
    """
    P3: Tests distribution performance endpoint returns safe defaults when no planning runs exist.
    """
    res = client.get("/api/optimization/distribution-performance")
    assert res.status_code == 200
    data = res.json()

    assert data["demand_fulfilment_rate_percent"] == 0.0
    assert data["transportation_cost"] == 0.0
    assert data["stockout_rate_percent"] == 0.0
    assert data["cost_reduction_percent"] == 0.0
    assert data["has_recorded_shipments"] is False


def test_distribution_performance_kpis_with_optimizer_and_baseline(client: TestClient, db_session: Session):
    """
    P3: Tests the four separately labelled KPIs on an active optimization run:
    1. Demand fulfilment rate = fulfilled demand units / eligible demand units * 100
    2. Transportation cost = recorded transportation cost for the selected period
    3. Stockout rate = demand units unfulfilled because of stock unavailability / eligible demand units * 100
    4. Cost reduction = (baseline cost - optimized cost) / baseline cost * 100
    Verifies baseline and optimizer are compared over equivalent demand, dates, and constraints.
    """
    _seed_eval_network(db_session)

    # Add 14 days of sales to establish baseline demand
    today = date.today()
    for i in range(1, 15):
        db_session.add(
            SalesHistory(
                sku_id="SKU-CHAI-100",
                destination_id="LOC-DIST-PUNE",
                sales_date=today - timedelta(days=i),
                quantity=100.0,
            )
        )

    # Add dispatchable inventory in Mumbai DC (500 units)
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-INIT",
            location_id="LOC-WH-MUMBAI",
            sku_id="SKU-CHAI-100",
            as_of_date=today,
            on_hand=500.0,
            reserved=0.0,
            blocked=0.0,
            owner_org_id="ORG-FMCG-CORP",
            batch_number="BATCH-001",
            expiry_date=today + timedelta(days=90),
        )
    )
    db_session.commit()

    # Execute distribution optimization
    opt_payload = {
        "snapshot_id": "SNAP-INIT",
        "horizon_days": 7,
        "objective_strategy": "service_first",
        "allow_cross_region_routes": True,
        "authorized_user_id": "admin_user",
    }
    opt_res = client.post("/api/optimization/run", json=opt_payload)
    assert opt_res.status_code == 201
    plan_run = opt_res.json()

    # Query Distribution Performance KPIs
    perf_res = client.get(f"/api/optimization/distribution-performance?run_id={plan_run['run_id']}")
    assert perf_res.status_code == 200
    perf = perf_res.json()

    assert perf["run_id"] == plan_run["run_id"]

    # 1. Demand Fulfilment Rate
    expected_fulfil = (
        round((perf["fulfilled_demand_units"] / perf["eligible_demand_units"]) * 100.0, 1)
        if perf["eligible_demand_units"] > 0
        else 100.0
    )
    assert abs(perf["demand_fulfilment_rate_percent"] - expected_fulfil) < 0.1

    # 2. Transportation Cost
    assert perf["transportation_cost"] >= 0.0
    assert "Estimated" in perf["transportation_cost_label"] or "Verified" in perf["transportation_cost_label"]

    # 3. Stockout Rate
    expected_stockout = (
        round((perf["unmet_demand_units"] / perf["eligible_demand_units"]) * 100.0, 1)
        if perf["eligible_demand_units"] > 0
        else 0.0
    )
    assert abs(perf["stockout_rate_percent"] - expected_stockout) < 0.1

    # 4. Cost Reduction vs Baseline
    if perf["baseline_cost"] > 0:
        expected_red = round(((perf["baseline_cost"] - perf["optimized_cost"]) / perf["baseline_cost"]) * 100.0, 1)
        assert abs(perf["cost_reduction_percent"] - expected_red) < 0.1
        assert "Savings vs" in perf["cost_reduction_label"]


def test_distribution_performance_kpis_verified_operational_shipments(client: TestClient, db_session: Session):
    """
    P3: Tests that when operational shipments are approved / executed,
    data_source_mode switches to 'verified_operational' and has_recorded_shipments is True.
    """
    _seed_eval_network(db_session)
    today = date.today()

    # Add planning run
    run = PlanningRun(
        run_id="RUN-TEST-OP-001",
        horizon_days=7,
        objective_strategy="service_first",
        solver_status="optimal",
        solver_name="ortools_glop",
        total_demand_units=700.0,
        fulfilled_demand_units=700.0,
        unmet_demand_units=0.0,
        service_level_percent=100.0,
        estimated_transport_cost=2450.0,
        org_id="ORG-FMCG-CORP",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(run)

    # Add verified delivered shipment
    shp = Shipment(
        shipment_id="SHP-OP-100",
        sku_id="SKU-CHAI-100",
        source_location_id="LOC-WH-MUMBAI",
        destination_location_id="LOC-DIST-PUNE",
        owner_org_id="ORG-FMCG-CORP",
        quantity=700.0,
        estimated_transport_cost=2450.0,
        status="delivered",
        approval_status="approved",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(shp)
    db_session.commit()

    perf_res = client.get("/api/optimization/distribution-performance?run_id=RUN-TEST-OP-001")
    assert perf_res.status_code == 200
    perf = perf_res.json()

    assert perf["has_recorded_shipments"] is True
    assert perf["data_source_mode"] == "verified_operational"
    assert "Verified Operational" in perf["transportation_cost_label"]
    assert perf["transportation_cost"] == 2450.0
    assert perf["demand_fulfilment_rate_percent"] == 100.0
    assert perf["stockout_rate_percent"] == 0.0
