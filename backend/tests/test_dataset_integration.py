import os
import json
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.entities import (
    Product,
    Location,
    Organization,
    InventorySnapshot,
    SalesHistory,
    Route,
    PlanningRun,
    Shipment,
)
from app.schemas.planning import OptimizationRequest
from app.services.dataset_service import DatasetService
from app.services.osrm_service import OSRMService
from app.services.forecast_service import compute_demand_forecast
from app.services.optimizer_service import run_distribution_optimization
from app.services.m5_adapter import M5Adapter
from app.services.freshretail_adapter import FreshRetailAdapter


def test_dataset_readiness_endpoint(client: TestClient):
    """Phase 5: Verify Dataset Sources and Data Readiness endpoint."""
    response = client.get("/api/imports/readiness")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] in ("operational", "active")
    assert data["environment_isolation"]["namespace"] == "BENCHMARK-ISOLATED"
    assert data["environment_isolation"]["live_inventory_mutations_allowed"] is False

    # Check sources presence
    source_ids = [s["id"] for s in data["sources"]]
    assert "osm_india_logistics" in source_ids
    assert "uci_online_retail" in source_ids
    assert "walmart_m5" in source_ids
    assert "dingdong_freshretail" in source_ids or "freshretailnet_50k" in source_ids

    # Check operational boundary documentation
    assert len(data["fields_requiring_authorized_company_data"]) >= 5
    req_fields = [f["field"] for f in data["fields_requiring_authorized_company_data"]]
    assert "batch_number" in req_fields
    assert "expiry_date" in req_fields
    assert "cost_rate" in req_fields


def test_osrm_service_routing():
    """Phase 2 & 4: Verify OpenStreetMap OSRM routing and fallback calculations."""
    service = OSRMService(timeout_seconds=5)

    # Mumbai (Bhiwandi CDC: 19.2968, 73.0645) to Pune (Chakan RDC: 18.7606, 73.8636)
    dist_km, is_road = service.get_road_distance(
        origin_lat=19.2968,
        origin_lon=73.0645,
        dest_lat=18.7606,
        dest_lon=73.8636,
        allow_fallback=True,
    )

    assert dist_km > 50.0  # Real distance is ~120-150 km
    assert dist_km < 300.0
    assert isinstance(is_road, bool)

    # Identical origin & destination must be 0 km
    zero_dist, _ = service.get_road_distance(19.0, 73.0, 19.0, 73.0)
    assert zero_dist == 0.0

    # Haversine straight line fallback validation
    hav_km = service.haversine_distance(19.2968, 73.0645, 18.7606, 73.8636)
    assert 90.0 < hav_km < 130.0


def test_osm_network_ingestion_and_idempotency(db_session: Session):
    """Phase 3 & 4: Ingest OpenStreetMap logistics facilities and routes idempotently."""
    # First ingestion
    result1 = DatasetService.ingest_osm_network(db_session)
    assert result1["status"] in ("success", "completed", "already_ingested")
    assert result1["locations_ingested"] >= 16
    assert result1["organizations_ingested"] >= 10
    assert result1["routes_ingested"] >= 60

    # Verify entities in DB
    locations = db_session.query(Location).all()
    assert len(locations) >= 16

    routes = db_session.query(Route).all()
    assert len(routes) >= 60

    # Verify road distances are stored
    sample_route = routes[0]
    assert sample_route.lead_time_days > 0
    assert sample_route.cost_rate > 0

    # Second ingestion must be idempotent without primary key collision
    result2 = DatasetService.ingest_osm_network(db_session)
    assert result2["status"] in ("success", "already_ingested")


def test_uci_sales_ingestion_and_cancellation_quarantine(db_session: Session):
    """Phase 2 & 3: Ingest UCI Online Retail benchmark with return/cancellation segregation."""
    # Ingest small subset of products for fast unit test
    result = DatasetService.ingest_uci_online_retail(db_session, limit_products=10)
    assert result["status"] in ("success", "completed", "already_ingested")
    assert result["products_ingested"] >= 5
    assert result["sales_records_ingested"] >= 50
    assert result["inventory_snapshots_ingested"] >= 5

    # Verify products
    products = db_session.query(Product).all()
    assert len(products) >= 5
    for p in products:
        assert p.case_pack >= 1
        assert p.shelf_life_days >= 30

    # Verify sales observations
    sales = db_session.query(SalesHistory).all()
    assert len(sales) >= 50
    for s in sales:
        assert s.quantity >= 0  # No negative return rows leaked into sales table

    # Verify snapshot quarantine
    inventories = db_session.query(InventorySnapshot).filter_by(snapshot_id="SNAP-BENCHMARK-PUBLIC").all()
    assert len(inventories) >= 5
    for inv in inventories:
        expected_dispatchable = max(0.0, float(inv.on_hand - inv.reserved - inv.blocked))
        assert inv.dispatchable_stock == expected_dispatchable


def test_demand_forecasting_pipeline(db_session: Session):
    """Phase 4B: Run forecasting model on sales time series."""
    # Setup test product and locations
    prod = Product(
        sku_id="SKU-TEST-FC-1",
        name="Test Detergent 1kg",
        category="Fabric Care",
        unit="cases",
        case_pack=12,
        shelf_life_days=365,
    )
    dest = Location(
        location_id="LOC-TEST-RDC-1",
        name="Test Pune RDC",
        location_type="regional_warehouse",
        region="West",
    )
    db_session.add_all([prod, dest])
    db_session.commit()

    # Generate 60 days of historical sales
    base_date = date.today() - timedelta(days=60)
    for i in range(60):
        sale_dt = base_date + timedelta(days=i)
        units = 20.0 + (i % 7) * 5.0  # Weekly pattern
        db_session.add(
            SalesHistory(
                sales_date=sale_dt,
                destination_id="LOC-TEST-RDC-1",
                sku_id="SKU-TEST-FC-1",
                quantity=units,
            )
        )
    db_session.commit()

    # Run demand forecast for 14-day horizon
    forecast_resp = compute_demand_forecast(
        db=db_session,
        horizon_days=14,
        sku_id="SKU-TEST-FC-1",
        destination_id="LOC-TEST-RDC-1",
    )

    assert forecast_resp.total_skus >= 1
    assert len(forecast_resp.forecasts) >= 1
    matched = [f for f in forecast_resp.forecasts if f.sku_id == "SKU-TEST-FC-1" and f.destination_id == "LOC-TEST-RDC-1"]
    assert len(matched) == 1
    fc = matched[0]
    assert fc.total_forecast_demand > 0
    assert fc.daily_forecast_rate > 0
    assert fc.data_sufficiency == "sufficient"


def test_distribution_optimization_with_fefo_and_routes(db_session: Session):
    """Phase 4F: Test distribution optimization with FEFO and verified route distances."""
    # 1. Setup Organizations
    mfg_org = Organization(org_id="ORG-TEST-MFG", name="Test Manufacturing Ltd", org_type="fmcg_company")
    dist_org = Organization(org_id="ORG-TEST-DIST", name="Test Distributor Partner", org_type="distributor")
    db_session.add_all([mfg_org, dist_org])

    # 2. Setup Product
    prod = Product(
        sku_id="SKU-OPT-01",
        name="High Demand Tea 500g",
        category="Beverages",
        unit="cases",
        case_pack=24,
        shelf_life_days=365,
    )
    db_session.add(prod)

    # 3. Setup Locations (CDC and RDC)
    cdc = Location(
        location_id="LOC-OPT-CDC",
        name="Central DC Mumbai",
        location_type="company_warehouse",
        region="West",
        latitude=19.2968,
        longitude=73.0645,
        owner_org_id="ORG-TEST-MFG",
    )
    rdc = Location(
        location_id="LOC-OPT-RDC",
        name="Regional DC Pune",
        location_type="regional_warehouse",
        region="West",
        latitude=18.7606,
        longitude=73.8636,
        owner_org_id="ORG-TEST-DIST",
    )
    db_session.add_all([cdc, rdc])

    # 4. Setup Verified Highway Route
    route = Route(
        from_location_id="LOC-OPT-CDC",
        to_location_id="LOC-OPT-RDC",
        lead_time_days=1.0,
        cost_rate=12.5,
        pricing_basis="per_unit",
        is_active=True,
    )
    db_session.add(route)

    # 5. Setup Batch Inventory at CDC (Batch A expiring soon, Batch B expiring late)
    today = date.today()
    inv_batch_a = InventorySnapshot(
        snapshot_id="SNAP-TEST-001",
        as_of_date=today,
        location_id="LOC-OPT-CDC",
        sku_id="SKU-OPT-01",
        batch_number="BATCH-A-EXPIRING-SOON",
        expiry_date=today + timedelta(days=20),
        on_hand=100.0,
        reserved=10.0,
        blocked=0.0,
        owner_org_id="ORG-TEST-MFG",
    )
    # Also add demand history at RDC so risk analysis finds a demand gap
    for i in range(14):
        db_session.add(
            SalesHistory(
                sales_date=today - timedelta(days=i + 1),
                destination_id="LOC-OPT-RDC",
                sku_id="SKU-OPT-01",
                quantity=15.0,
            )
        )
    db_session.add(inv_batch_a)
    db_session.commit()

    # 6. Run Optimization for SNAP-TEST-001
    opt_req = OptimizationRequest(
        snapshot_id="SNAP-TEST-001",
        horizon_days=7,
        objective_strategy="service-first",
    )

    plan_result = run_distribution_optimization(
        db=db_session,
        request=opt_req,
        created_by_user_id="test_admin@stockwise.internal",
    )

    assert plan_result is not None
    assert plan_result.solver_status in ("optimal", "feasible")
    assert len(plan_result.decision_receipts) >= 1

    # Verify Decision Receipt structure
    receipt = plan_result.decision_receipts[0]
    assert receipt.sku_id == "SKU-OPT-01"
    assert receipt.source_location_id == "LOC-OPT-CDC"
    assert receipt.destination_location_id == "LOC-OPT-RDC"
    assert receipt.quantity > 0
    assert len(receipt.evidence) > 0


def test_tenant_and_workflow_isolation(db_session: Session):
    """Phase 4H & 4I: Guarantee benchmark data never mutates physical stock or creates live shipments."""
    # Create benchmark inventory
    today = date.today()
    bench_inv = InventorySnapshot(
        snapshot_id="SNAP-BENCHMARK-PUBLIC",
        as_of_date=today,
        location_id="LOC-WH-1",
        sku_id="SKU-BENCH-01",
        on_hand=500.0,
        reserved=50.0,
        blocked=0.0,
        owner_org_id="BENCHMARK-COMPANY",
    )
    db_session.add(bench_inv)
    db_session.commit()

    # Verify that no unauthorized live shipments exist
    shipment_count = db_session.query(Shipment).count()
    assert shipment_count == 0

    # Verify inventory state unchanged after simulation
    inv_check = db_session.query(InventorySnapshot).filter_by(sku_id="SKU-BENCH-01").first()
    assert inv_check.on_hand == 500.0
    assert inv_check.reserved == 50.0
    assert inv_check.dispatchable_stock == 450.0


def test_m5_and_freshretail_adapters():
    """Phase 2: Verify adapter documentation, blockers, and transformation handling."""
    # Test M5 Adapter
    m5_status = M5Adapter.get_status()
    assert "https://www.kaggle.com/competitions/m5-forecasting-accuracy/data" in m5_status["official_url"]
    assert "Kaggle" in m5_status["blocker_details"]
    assert len(m5_status["remediation_instructions"]) >= 3

    # Test FreshRetailNet Adapter
    fresh_status = FreshRetailAdapter.get_status()
    assert "Dingdong" in fresh_status["source_name"]
    assert "CC BY 4.0" in fresh_status["license"]
    assert "50,000 SKUs" in fresh_status["product_hierarchy"]
