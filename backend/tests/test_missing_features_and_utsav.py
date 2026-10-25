import io
import json
from datetime import datetime, timezone, timedelta, date
import pytest
from fastapi.testclient import TestClient

from app.models.entities import (
    Organization,
    Location,
    Product,
    Route,
    InventorySnapshot,
    SalesHistory,
    Shipment,
    PlanningRun,
)
from app.services.inventory_service import (
    compute_dispatchable_stock,
    compute_projected_available_stock,
    compute_stock_cover_days,
    compute_safety_stock,
    compute_target_stock,
    compute_replenishment_gap,
    compute_excess_stock,
    evaluate_batch_shelf_life,
    is_distributor_owned_stock,
)


def _seed_test_network(client: TestClient):
    """Seed standard FMCG test network."""
    # 1. Organizations
    client.post("/api/organizations", json={"org_id": "ORG-CORP", "name": "Apex FMCG India", "org_type": "fmcg_company"})
    client.post("/api/organizations", json={"org_id": "ORG-DIST-NORTH", "name": "North Distributors Ltd", "org_type": "independent_distributor"})
    client.post("/api/organizations", json={"org_id": "ORG-LOG", "name": "TransIndia Logistics", "org_type": "logistics_provider"})

    # 2. Locations
    # Central Plant (Mumbai)
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-MUM-PLANT",
            "name": "Mumbai Plant",
            "location_type": "manufacturing_plant",
            "region": "West",
            "city": "Mumbai",
            "owner_org_id": "ORG-CORP",
            "operator_org_id": "ORG-CORP",
            "storage_capacity_units": 100000,
            "dispatch_capacity_daily": 10000,
            "is_active": True,
        },
    )
    # Regional Warehouse (Delhi)
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-DEL-RDC",
            "name": "Delhi Regional DC",
            "location_type": "regional_warehouse",
            "region": "North",
            "city": "Delhi",
            "owner_org_id": "ORG-CORP",
            "operator_org_id": "ORG-CORP",
            "storage_capacity_units": 50000,
            "dispatch_capacity_daily": 5000,
            "is_active": True,
        },
    )
    # Retail Destination (Delhi Retail hub)
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-DEL-RETAIL",
            "name": "Delhi Superstore Hub",
            "location_type": "retail_destination",
            "region": "North",
            "city": "Delhi",
            "owner_org_id": "ORG-DIST-NORTH",
            "operator_org_id": "ORG-DIST-NORTH",
            "storage_capacity_units": 10000,
            "dispatch_capacity_daily": 1000,
            "is_active": True,
        },
    )

    # 3. Products
    products_csv = "sku_id,name,category,unit,case_pack,shelf_life_days\n" \
                   "SKU-ATTA-01,Chakki Atta 10kg,Staples,cases,10,180\n" \
                   "SKU-OIL-02,Mustard Oil 1L,Edible Oils,cases,12,270\n"
    client.post(
        "/api/imports/products",
        files={"file": ("products.csv", io.BytesIO(products_csv.encode("utf-8")), "text/csv")},
    )

    # 4. Permitted Routes
    client.post(
        "/api/network/routes",
        json={
            "from_location_id": "LOC-MUM-PLANT",
            "to_location_id": "LOC-DEL-RETAIL",
            "lead_time_days": 3.0,
            "cost_rate": 25.0,
            "capacity_units": 5000.0,
            "is_active": True,
        },
    )
    client.post(
        "/api/network/routes",
        json={
            "from_location_id": "LOC-DEL-RDC",
            "to_location_id": "LOC-DEL-RETAIL",
            "lead_time_days": 1.0,
            "cost_rate": 10.0,
            "capacity_units": 3000.0,
            "is_active": True,
        },
    )


# ---------------------------------------------------------------------------
# Feature 1 & 2: Complete CSV/Excel Import & Data Validation with Preview
# ---------------------------------------------------------------------------

def test_feature1_and_2_import_preview_and_validation(client: TestClient, db_session):
    """Verify preview mode, blocking errors vs warnings, and error report downloads."""
    # 1. Preview valid products
    valid_csv = "sku_id,name,category,unit,case_pack,shelf_life_days\n" \
                "SKU-TEA-03,Premium CTC Tea 500g,Beverages,cases,24,365\n"
    res = client.post(
        "/api/imports/products/preview",
        files={"file": ("products.csv", io.BytesIO(valid_csv.encode("utf-8")), "text/csv")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "preview_valid"
    assert data["total_rows"] == 1
    assert data["valid_rows"] == 1
    assert data["rejected_rows"] == 0
    assert len(data["errors"]) == 0
    # Confirm NO DB changes were written in preview mode
    assert db_session.query(Product).filter(Product.sku_id == "SKU-TEA-03").first() is None

    # 2. Preview invalid products (missing required fields, negative case_pack)
    invalid_csv = "sku_id,name,category,unit,case_pack,shelf_life_days\n" \
                  ",Missing SKU Name,Beverages,cases,10,365\n" \
                  "SKU-BAD-01,Bad Product,Beverages,cases,-5,365\n"
    res_inv = client.post(
        "/api/imports/products/preview",
        files={"file": ("bad_products.csv", io.BytesIO(invalid_csv.encode("utf-8")), "text/csv")},
    )
    assert res_inv.status_code == 200
    data_inv = res_inv.json()
    assert data_inv["status"] in ("preview_partial", "preview_failed")
    assert data_inv["rejected_rows"] >= 2
    assert len(data_inv["errors"]) >= 2
    err_reasons = [e["error_reason"] for e in data_inv["errors"]]
    assert any("required" in r.lower() for r in err_reasons)
    assert any("must be at least 1" in r for r in err_reasons)

    # 3. Commit actual import
    res_commit = client.post(
        "/api/imports/products",
        files={"file": ("products.csv", io.BytesIO(valid_csv.encode("utf-8")), "text/csv")},
    )
    assert res_commit.status_code == 200
    assert db_session.query(Product).filter(Product.sku_id == "SKU-TEA-03").first() is not None

    # 4. Duplicate import detection & error CSV download
    dup_csv = "sku_id,name,category,unit,case_pack,shelf_life_days\n" \
              "SKU-DUP-01,Product One,Beverages,cases,24,365\n" \
              "SKU-DUP-01,Product Two,Beverages,cases,24,365\n"
    res_dup = client.post(
        "/api/imports/products",
        files={"file": ("dup_products.csv", io.BytesIO(dup_csv.encode("utf-8")), "text/csv")},
    )
    assert res_dup.status_code == 200
    dup_data = res_dup.json()
    assert dup_data["status"] in ("partial", "failed")
    assert dup_data["rejected_rows"] >= 1
    run_id = dup_data["run_id"]

    # Download error report CSV
    res_err_csv = client.get(f"/api/imports/{run_id}/errors.csv")
    assert res_err_csv.status_code == 200
    assert res_err_csv.headers["content-type"].startswith("text/csv")
    assert "row_number,field_name,rejected_value,error_reason,error_code,recommended_correction" in res_err_csv.text
    assert "Duplicate" in res_err_csv.text


# ---------------------------------------------------------------------------
# Feature 3: Inventory Calculation Engine (All 8 pure formulas tested)
# ---------------------------------------------------------------------------

def test_feature3_inventory_calculation_engine_formulas():
    """Verify unified inventory accounting service pure formulas."""
    # 1. Dispatchable stock formula: max(0, on_hand - reserved - blocked)
    assert compute_dispatchable_stock(100.0, 20.0, 10.0) == 70.0
    assert compute_dispatchable_stock(50.0, 40.0, 20.0) == 0.0  # no negative dispatchable

    # 2. Projected available: on_hand - reserved - blocked + incoming
    proj_stock, inc_counted = compute_projected_available_stock(100.0, 10.0, 5.0, 40.0)
    assert proj_stock == 125.0
    assert inc_counted is True

    # 3. Stock cover days: available / daily_demand
    assert compute_stock_cover_days(100.0, 20.0) == 5.0
    assert compute_stock_cover_days(0.0, 20.0) == 0.0
    assert compute_stock_cover_days(100.0, 0.0) == 999.0  # infinite cover if zero demand

    # 4. Safety stock calculation
    ss = compute_safety_stock(daily_demand=10.0, buffer_days=3.0)
    assert ss == 30.0

    # 5. Target stock: demand during lead time + safety stock
    target = compute_target_stock(daily_demand=10.0, horizon_days=7, buffer_days=3.0)
    assert target == 100.0

    # 6. Replenishment gap: max(0, target - available)
    assert compute_replenishment_gap(100.0, 60.0) == 40.0
    assert compute_replenishment_gap(100.0, 120.0) == 0.0

    # 7. Excess stock: max(0, available - target)
    assert compute_excess_stock(125.0, 100.0) == 25.0
    assert compute_excess_stock(80.0, 100.0) == 0.0

    # 8. Batch shelf life evaluation
    today = datetime.now(timezone.utc)
    expired = today - timedelta(days=5)
    near_expiry = today + timedelta(days=20)
    fresh = today + timedelta(days=120)

    res_exp = evaluate_batch_shelf_life(expired)
    assert res_exp["risk_flag"] == "expired_blocked"
    assert res_exp["is_expired"] is True

    res_near = evaluate_batch_shelf_life(near_expiry)
    assert res_near["risk_flag"] in ("critical_expiry_window", "nearing_expiry_monitor")

    res_fresh = evaluate_batch_shelf_life(fresh)
    assert res_fresh["risk_flag"] == "healthy_shelf_life"

    # Distributor stock protection
    assert is_distributor_owned_stock("independent_distributor") is True
    assert is_distributor_owned_stock("fmcg_company") is False


# ---------------------------------------------------------------------------
# Feature 4: Demand Forecasting with Chronological Holdout & Seasonal Naive
# ---------------------------------------------------------------------------

def test_feature4_demand_forecasting_holdout_and_seasonal_naive(client: TestClient, db_session):
    """Verify forecasting service with 7-day cyclical seasonality and temporal holdout."""
    _seed_test_network(client)

    # Seed 35 days of sales history with a distinct 7-day cyclical pattern
    base_date = date(2026, 9, 1)
    for day in range(35):
        dt = base_date + timedelta(days=day)
        day_of_week = dt.weekday()
        qty = 40.0 if day_of_week in (5, 6) else 15.0
        sale = SalesHistory(
            sku_id="SKU-ATTA-01",
            destination_id="LOC-DEL-RETAIL",
            sales_date=dt,
            quantity=qty,
        )
        db_session.add(sale)
    db_session.commit()

    # Request 7-day baseline forecast
    res = client.get("/api/forecast?horizon_days=7")
    assert res.status_code == 200
    data = res.json()
    forecasts = data["forecasts"]
    assert len(forecasts) >= 1

    item = next(f for f in forecasts if f["sku_id"] == "SKU-ATTA-01" and f["destination_id"] == "LOC-DEL-RETAIL")
    assert item["total_forecast_demand"] > 0
    assert item["daily_forecast_rate"] > 0
    assert item["data_sufficiency"] == "sufficient"
    assert item["training_window"] is not None
    assert item["evaluation_window"] is not None
    assert item["forecast_method"] in ("seasonal_naive_7d", "moving_average_7d")
    assert item["wape"] is not None


# ---------------------------------------------------------------------------
# Feature 5 & 6: Stockout Risk Detection, Target Stock, and Replenishment Gap
# ---------------------------------------------------------------------------

def test_feature5_and_6_stockout_risk_and_replenishment_gap(client: TestClient, db_session):
    """Verify stockout risk levels, lead time vs stock cover, and replenishment gap."""
    _seed_test_network(client)
    base_date = date(2026, 9, 1)

    # Seed sales (daily demand = 20 cases)
    for day in range(14):
        db_session.add(
            SalesHistory(
                sku_id="SKU-ATTA-01",
                destination_id="LOC-DEL-RETAIL",
                sales_date=base_date + timedelta(days=day),
                quantity=20.0,
            )
        )
    # Seed very low stock at destination (10 units = 0.5 days cover; min lead time is 1 day -> critical risk)
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-TEST-01",
            sku_id="SKU-ATTA-01",
            location_id="LOC-DEL-RETAIL",
            on_hand=10.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            as_of_date=base_date + timedelta(days=14),
        )
    )
    db_session.commit()

    res = client.get("/api/risk/analysis?horizon_days=7")
    assert res.status_code == 200
    data = res.json()
    risks = data["items"]
    item = next(r for r in risks if r["sku_id"] == "SKU-ATTA-01" and r["destination_id"] == "LOC-DEL-RETAIL")

    assert item["risk_level"] == "critical"
    assert item["cover_days"] < item["earliest_replenishment_lead_time_days"]
    assert item["target_stock"] > item["dispatchable_stock"]
    assert item["replenishment_need"] > 0
    assert item["expected_stockout_window"] is not None
    assert "unfulfillable_demand" in item


# ---------------------------------------------------------------------------
# Feature 7 & 10: Google OR-Tools Optimizer & Solver Benchmark Comparison
# ---------------------------------------------------------------------------

def test_feature7_and_10_ortools_optimizer_and_benchmark(client: TestClient, db_session):
    """Verify OR-Tools 2-stage solver, feasibility, and side-by-side benchmark with HiGHS."""
    _seed_test_network(client)
    base_date = date(2026, 9, 1)

    # Seed ample stock at Mumbai Plant (1000 units) and Delhi RDC (500 units)
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-DEST-01",
            sku_id="SKU-ATTA-01",
            location_id="LOC-MUM-PLANT",
            on_hand=1000.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            as_of_date=base_date + timedelta(days=14),
        )
    )
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-DEST-01",
            sku_id="SKU-ATTA-01",
            location_id="LOC-DEL-RDC",
            on_hand=500.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            as_of_date=base_date + timedelta(days=14),
        )
    )
    # Destination stock low (demand = 20/day * 7d = 140 needed)
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-DEST-01",
            sku_id="SKU-ATTA-01",
            location_id="LOC-DEL-RETAIL",
            on_hand=20.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            as_of_date=base_date + timedelta(days=14),
        )
    )
    # Seed 14 days of sales
    for day in range(14):
        db_session.add(
            SalesHistory(
                sku_id="SKU-ATTA-01",
                destination_id="LOC-DEL-RETAIL",
                sales_date=base_date + timedelta(days=day),
                quantity=20.0,
            )
        )
    db_session.commit()

    # 1. Run optimization with Google OR-Tools
    req = {
        "snapshot_id": "SNAP-DEST-01",
        "horizon_days": 7,
        "objective_strategy": "service_first",
        "solver_preference": "ortools",
    }
    res = client.post("/api/optimization/run", json=req)
    assert res.status_code == 201
    plan = res.json()
    assert plan["solver_status"] == "optimal"
    assert "ortools" in plan["solver_name"]
    assert plan["service_level_percent"] == 100.0
    assert len(plan["recommended_shipments"]) > 0

    # 2. Run solver benchmark comparison (OR-Tools vs HiGHS vs Nearest Baseline)
    res_bench = client.post("/api/optimization/benchmark", json=req)
    assert res_bench.status_code == 200
    bench = res_bench.json()
    assert "ortools_metrics" in bench
    assert "highs_metrics" in bench
    assert "baseline_metrics" in bench

    ortools_metrics = bench["ortools_metrics"]
    highs_metrics = bench["highs_metrics"]
    base_metrics = bench["baseline_metrics"]

    # Both LP solvers find 100% service level on this deterministic test network
    assert ortools_metrics["service_level_percent"] == 100.0
    assert highs_metrics["service_level_percent"] == 100.0
    assert base_metrics["service_level_percent"] > 0.0
    assert bench["comparison_summary"] is not None


# ---------------------------------------------------------------------------
# Feature 8 & 9: Decision Receipts & Transportation Cost in INR
# ---------------------------------------------------------------------------

def test_feature8_and_9_decision_receipts_and_inr(client: TestClient, db_session):
    """Verify decision receipts contain grounded reasons, currency INR, and solver metadata."""
    _seed_test_network(client)
    base_date = date(2026, 9, 1)

    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-SRC",
            sku_id="SKU-ATTA-01",
            location_id="LOC-DEL-RDC",
            on_hand=500.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            as_of_date=base_date + timedelta(days=14),
        )
    )
    for day in range(14):
        db_session.add(
            SalesHistory(
                sku_id="SKU-ATTA-01",
                destination_id="LOC-DEL-RETAIL",
                sales_date=base_date + timedelta(days=day),
                quantity=10.0,
            )
        )
    db_session.commit()

    res = client.post(
        "/api/optimization/run",
        json={"snapshot_id": "SNAP-SRC", "horizon_days": 7, "objective_strategy": "service_first"},
    )
    assert res.status_code == 201
    plan = res.json()
    assert len(plan["decision_receipts"]) > 0

    receipt = plan["decision_receipts"][0]
    assert receipt["currency"] == "INR"
    assert receipt["solver_name"] is not None
    assert receipt["expected_arrival_date"] is not None
    assert receipt["quantity"] > 0
    assert "Allocated" in receipt["evidence"]
    assert receipt["solver_status"] == "optimal"


# ---------------------------------------------------------------------------
# Feature 11: Approval Workflow & Live Stale-Plan Rejection (HTTP 409)
# ---------------------------------------------------------------------------

def test_feature11_stale_plan_rejection_concurrency(client: TestClient, db_session):
    """Verify approving a shipment when live stock drops triggers HTTP 409 Conflict."""
    _seed_test_network(client)
    base_date = date(2026, 9, 1)

    # 1. Seed exact stock at RDC = 50 cases
    snap = InventorySnapshot(
        snapshot_id="SNAP-CONC-01",
        sku_id="SKU-ATTA-01",
        location_id="LOC-DEL-RDC",
        on_hand=50.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        as_of_date=base_date + timedelta(days=14),
    )
    db_session.add(snap)
    for day in range(14):
        db_session.add(
            SalesHistory(
                sku_id="SKU-ATTA-01",
                destination_id="LOC-DEL-RETAIL",
                sales_date=base_date + timedelta(days=day),
                quantity=10.0,
            )
        )
    db_session.commit()

    # 2. Run optimizer to create proposed shipment of 50 units
    res_plan = client.post(
        "/api/optimization/run",
        json={"snapshot_id": "SNAP-CONC-01", "horizon_days": 7, "objective_strategy": "service_first"},
    )
    assert res_plan.status_code == 201
    plan = res_plan.json()
    shipment_id = plan["recommended_shipments"][0]["shipment_id"]

    # 3. Simulate concurrent consumption: Block 45 units in inventory snapshot leaving only 5 dispatchable!
    live_snap = db_session.query(InventorySnapshot).filter(
        InventorySnapshot.sku_id == "SKU-ATTA-01",
        InventorySnapshot.location_id == "LOC-DEL-RDC",
    ).first()
    live_snap.blocked = 45.0
    db_session.commit()

    # 4. Attempt to approve proposed shipment of 50 units -> must be rejected with HTTP 409 Conflict
    res_app = client.post(
        f"/api/shipments/{shipment_id}/approve",
        json={
            "approved": True,
            "authorized_user_id": "SUPPLY-PLANNER-01",
            "notes": "Approving shipment after concurrent change",
        },
    )
    assert res_app.status_code == 409
    err = res_app.json()
    assert "live dispatchable stock" in err["detail"].lower()
    assert "is insufficient" in err["detail"]


# ---------------------------------------------------------------------------
# Feature 12: CSV Export Endpoints
# ---------------------------------------------------------------------------

def test_feature12_csv_exports(client: TestClient, db_session):
    """Verify CSV exports for shipments, receipts, unmet demand, and risk analysis."""
    _seed_test_network(client)
    base_date = date(2026, 9, 1)

    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-EXPORT",
            sku_id="SKU-ATTA-01",
            location_id="LOC-DEL-RDC",
            on_hand=500.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            as_of_date=base_date + timedelta(days=14),
        )
    )
    for day in range(14):
        db_session.add(
            SalesHistory(
                sku_id="SKU-ATTA-01",
                destination_id="LOC-DEL-RETAIL",
                sales_date=base_date + timedelta(days=day),
                quantity=10.0,
            )
        )
    db_session.commit()

    res = client.post(
        "/api/optimization/run",
        json={"snapshot_id": "SNAP-EXPORT", "horizon_days": 7, "objective_strategy": "service_first"},
    )
    assert res.status_code == 201
    run_id = res.json()["run_id"]

    # 1. Export shipments CSV
    res_shp_csv = client.get(f"/api/optimization/runs/{run_id}/export/shipments.csv")
    assert res_shp_csv.status_code == 200
    assert res_shp_csv.headers["content-type"].startswith("text/csv")
    assert "shipment_id,planning_run_id,sku_id,product_name" in res_shp_csv.text

    # 2. Export decision receipts CSV
    res_rcp_csv = client.get(f"/api/optimization/runs/{run_id}/export/receipts.csv")
    assert res_rcp_csv.status_code == 200
    assert "recommendation_id,planning_run_id,sku_id,product_name" in res_rcp_csv.text

    # 3. Export unmet demand CSV
    res_unm_csv = client.get(f"/api/optimization/runs/{run_id}/export/unmet-demand.csv")
    assert res_unm_csv.status_code == 200
    assert "sku_id,product_name,destination_id" in res_unm_csv.text

    # 4. Export risk analysis CSV
    res_risk_csv = client.get("/api/risk/export/analysis.csv?horizon_days=7")
    assert res_risk_csv.status_code == 200
    assert "sku_id,product_name,destination_id,destination_name" in res_risk_csv.text


# ---------------------------------------------------------------------------
# Feature 13: UtsavSense Festival-Aware Inventory Planning
# ---------------------------------------------------------------------------

def test_feature13_utsav_sense_festival_planning(client: TestClient, db_session):
    """Verify festival calendar, uplift scenarios, additional stock calculation, and festival optimization."""
    _seed_test_network(client)
    # 1. Seed festivals into test database and verify calendar
    from app.services.utsav_service import ensure_default_festivals
    ensure_default_festivals(db_session)
    res_events = client.get("/api/utsav/events")
    assert res_events.status_code == 200
    events = res_events.json()
    assert len(events) >= 3
    event_ids = [e["event_id"] for e in events]
    assert "FEST-DIWALI-2026" in event_ids
    assert "FEST-GANESH-2026" in event_ids

    # 2. Create custom regional festival (e.g., Onam)
    res_custom = client.post(
        "/api/utsav/events",
        json={
            "event_id": "FEST-ONAM-2026",
            "name": "Onam Harvest Festival",
            "description": "Kerala harvest festival with surge in Staples and Edible Oils",
            "start_date": "2026-08-25",
            "end_date": "2026-09-05",
            "regions": ["South"],
            "applicable_categories": ["Staples", "Edible Oils"],
            "default_uplift_percent": 30.0,
            "is_active": True,
        },
    )
    assert res_custom.status_code == 201

    # 3. Seed sales data and stock for Diwali uplift evaluation
    base_date = datetime.now(timezone.utc).date() - timedelta(days=14)
    for day in range(14):
        db_session.add(
            SalesHistory(
                sku_id="SKU-ATTA-01",
                destination_id="LOC-DEL-RETAIL",
                sales_date=base_date + timedelta(days=day),
                quantity=20.0,
            )
        )
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-UTSAV-01",
            sku_id="SKU-ATTA-01",
            location_id="LOC-DEL-RETAIL",
            on_hand=50.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            as_of_date=base_date + timedelta(days=14),
        )
    )
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-SRC-UTSAV",
            sku_id="SKU-ATTA-01",
            location_id="LOC-DEL-RDC",
            on_hand=1000.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            as_of_date=base_date + timedelta(days=14),
        )
    )
    db_session.commit()

    # 4. Calculate festival uplift under 'high' scenario (45% uplift) via GET endpoint
    res_uplift = client.get("/api/utsav/forecast-uplift?event_id=FEST-DIWALI-2026&scenario=high&horizon_days=7")
    assert res_uplift.status_code == 200
    data = res_uplift.json()
    assert data["event_name"] == "Diwali Festival of Lights 2026"
    assert data["uplift_percent"] == 67.5
    assert data["total_incremental_demand"] > 0
    assert len(data["items"]) >= 1

    uplift_item = next(
        i for i in data["items"]
        if i["sku_id"] == "SKU-ATTA-01" and i["destination_id"] == "LOC-DEL-RETAIL"
    )
    assert uplift_item["festival_demand"] > uplift_item["baseline_demand"]
    assert uplift_item["incremental_units"] > 0
    assert uplift_item["additional_stock_needed"] > 0

    # 5. Run festival optimization solve
    opt_req = {
        "event_id": "FEST-DIWALI-2026",
        "scenario": "high",
        "horizon_days": 7,
        "authorized_user_id": "UTSAV-PLANNER-01",
    }
    res_opt = client.post("/api/utsav/optimize", json=opt_req)
    assert res_opt.status_code == 201
    plan = res_opt.json()
    assert plan["planning_mode"] in ("utsav_sense", "festival_plan")
    assert plan["festival_event_id"] == "FEST-DIWALI-2026"
    assert plan["service_level_percent"] == 100.0
    assert len(plan["recommended_shipments"]) > 0

    # 6. Export festival plan CSV
    res_fest_csv = client.get("/api/utsav/events/FEST-DIWALI-2026/export.csv?scenario=high&horizon_days=7")
    assert res_fest_csv.status_code == 200
    assert "event_id,event_name,scenario,sku_id,product_name,category,destination_id" in res_fest_csv.text
    assert "FEST-DIWALI-2026" in res_fest_csv.text
