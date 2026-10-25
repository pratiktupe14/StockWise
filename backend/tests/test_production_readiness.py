"""
StockWise Phase 5: Production Readiness & End-to-End Regression Test Suite.

Verifies the 14-step operational journey, RBAC role enforcement, idempotency replays,
and system readiness probes on an isolated test database.
"""

import io
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.core.config import settings


def test_production_readiness_end_to_end_journey(client: TestClient):
    """
    Comprehensive 14-step End-to-End Regression Test:
    1. Import products, inventory, sales, warehouses, and routes.
    2. Preview validation errors without committing invalid data.
    3. Generate forecasts and stockout-risk analysis.
    4. Configure a UtsavSense festival scenario.
    5. Generate an optimized distribution plan.
    6. Compare OR-Tools, HiGHS, and the nearest-source baseline.
    7. Inspect Decision Receipts and export the plan.
    8. Approve a shipment after revalidating stock.
    9. Prepare dispatch and reserve inventory.
    10. Record physical dispatch.
    11. Confirm delivery and reconcile destination inventory.
    12. Verify shipment audit history.
    13. Confirm unauthorized users cannot perform restricted actions.
    14. Confirm all three portals remain functional.
    """

    # =========================================================================
    # Step 1: Import products, inventory, sales, warehouses, and routes
    # =========================================================================
    # Register Organizations
    client.post("/api/organizations", json={"org_id": "ORG-AMUL", "name": "Amul FMCG Corp", "org_type": "fmcg_company"})
    client.post("/api/organizations", json={"org_id": "ORG-VRL", "name": "VRL Logistics 3PL", "org_type": "logistics_provider"})
    client.post("/api/organizations", json={"org_id": "ORG-DIST-DEL", "name": "Delhi Super Distributors", "org_type": "independent_distributor"})

    # Register Network Locations
    client.post("/api/network/locations", json={"location_id": "LOC-AHM-PLANT", "name": "Ahmedabad Mother Dairy Plant", "location_type": "manufacturing_plant", "region": "West", "owner_org_id": "ORG-AMUL", "operating_status": "active"})
    client.post("/api/network/locations", json={"location_id": "LOC-DEL-RDC", "name": "Delhi Regional Distribution Center", "location_type": "company_warehouse", "region": "North", "owner_org_id": "ORG-AMUL", "operating_status": "active"})
    client.post("/api/network/locations", json={"location_id": "LOC-DEL-DIST", "name": "Delhi Primary Distributor", "location_type": "distributor", "region": "North", "owner_org_id": "ORG-DIST-DEL", "operating_status": "active"})

    # Register Route Lanes
    client.post("/api/network/routes", json={"from_location_id": "LOC-AHM-PLANT", "to_location_id": "LOC-DEL-RDC", "carrier_agency_id": "ORG-VRL", "lead_time_days": 2.0, "cost_rate": 8.5, "is_active": True})
    client.post("/api/network/routes", json={"from_location_id": "LOC-DEL-RDC", "to_location_id": "LOC-DEL-DIST", "carrier_agency_id": "ORG-VRL", "lead_time_days": 1.0, "cost_rate": 3.0, "is_active": True})

    # Bulk Import Products
    prod_csv = b"sku_id,name,category,unit,case_pack,shelf_life_days\nSKU-GHEE-1L,Amul Pure Ghee 1L,Dairy,cases,12,365\nSKU-BUTTER-500G,Amul Butter 500g,Dairy,cases,24,180\n"
    res_prod = client.post("/api/imports/products", files={"file": ("products.csv", io.BytesIO(prod_csv), "text/csv")})
    assert res_prod.status_code == 200
    assert res_prod.json()["valid_rows"] == 2

    # Bulk Import Inventory
    inv_csv = b"snapshot_id,sku_id,location_id,on_hand,reserved,blocked,confirmed_incoming,as_of_date\nSNAP-E2E,SKU-GHEE-1L,LOC-DEL-RDC,500,0,0,0,2026-10-24\nSNAP-E2E,SKU-GHEE-1L,LOC-DEL-DIST,20,0,0,0,2026-10-24\n"
    res_inv = client.post("/api/imports/inventory", files={"file": ("inv.csv", io.BytesIO(inv_csv), "text/csv")})
    assert res_inv.status_code == 200
    assert res_inv.json()["valid_rows"] == 2

    # Bulk Import Sales History (30 days of sales)
    sales_lines = ["sku_id,destination_id,sales_date,quantity"]
    base_dt = date(2026, 9, 20)
    for day in range(30):
        dt = base_dt + timedelta(days=day)
        qty = 25.0 if dt.weekday() in (5, 6) else 15.0
        sales_lines.append(f"SKU-GHEE-1L,LOC-DEL-DIST,{dt.isoformat()},{qty}")
    sales_csv = "\n".join(sales_lines).encode("utf-8")
    res_sales = client.post("/api/imports/sales", files={"file": ("sales.csv", io.BytesIO(sales_csv), "text/csv")})
    assert res_sales.status_code == 200
    assert res_sales.json()["valid_rows"] == 30

    # =========================================================================
    # Step 2: Preview validation errors without committing invalid data
    # =========================================================================
    invalid_csv = b"sku_id,name,category,unit,case_pack,shelf_life_days\n,Missing SKU,Dairy,cases,12,365\nSKU-BAD-SHELF,Bad Shelf,Dairy,cases,12,-10\n"
    res_preview = client.post("/api/imports/products/preview", files={"file": ("bad_prods.csv", io.BytesIO(invalid_csv), "text/csv")})
    assert res_preview.status_code == 200
    prev_data = res_preview.json()
    assert prev_data["rejected_rows"] >= 2
    assert prev_data["status"] in ("preview_partial", "preview_failed")
    # Verify no invalid products were committed
    prods_check = client.get("/api/products").json()
    assert not any(p["name"] == "Missing SKU" for p in prods_check)

    # =========================================================================
    # Step 3: Generate forecasts and stockout-risk analysis
    # =========================================================================
    res_forecast = client.get("/api/forecast?horizon_days=7")
    assert res_forecast.status_code == 200
    forecast_data = res_forecast.json()
    assert len(forecast_data["forecasts"]) >= 1
    ghee_fc = next(f for f in forecast_data["forecasts"] if f["sku_id"] == "SKU-GHEE-1L")
    assert ghee_fc["total_forecast_demand"] > 0

    res_risk = client.get("/api/inventory-risk?horizon_days=7")
    assert res_risk.status_code == 200
    risk_data = res_risk.json()
    assert len(risk_data["items"]) >= 1
    dist_risk = next(r for r in risk_data["items"] if r["destination_id"] == "LOC-DEL-DIST")
    # Low stock (20 on hand vs demand > 100) -> high risk
    assert dist_risk["risk_level"] in ("critical", "high", "medium")
    assert dist_risk["demand_gap"] >= 0

    # =========================================================================
    # Step 4: Configure a UtsavSense festival scenario
    # =========================================================================
    festival_payload = {
        "event_id": "FEST-DIWALI-2026",
        "name": "Diwali Deepavali Mega Festival",
        "start_date": "2026-11-01",
        "end_date": "2026-11-08",
        "regions": ["North"],
        "applicable_categories": ["Dairy"],
        "default_uplift_percent": 35.0,
    }
    res_fest = client.post("/api/utsav/events", json=festival_payload)
    assert res_fest.status_code == 201

    res_uplift = client.get("/api/utsav/forecast-uplift?event_id=FEST-DIWALI-2026&scenario=expected&horizon_days=7")
    assert res_uplift.status_code == 200
    uplift_data = res_uplift.json()
    assert uplift_data["uplift_percent"] >= 0.0

    # =========================================================================
    # Step 5: Generate an optimized distribution plan
    # =========================================================================
    opt_req = {
        "snapshot_id": "SNAP-E2E",
        "horizon_days": 7,
        "objective_strategy": "service-first",
        "solver_type": "ortools",
    }
    res_opt = client.post("/api/optimization/run", json=opt_req)
    assert res_opt.status_code == 201
    plan = res_opt.json()
    assert plan["solver_status"] == "optimal"
    assert "ortools" in plan["solver_name"]
    assert plan["service_level_percent"] == 100.0
    assert len(plan["recommended_shipments"]) > 0

    # =========================================================================
    # Step 6: Compare OR-Tools, HiGHS, and nearest-source baseline
    # =========================================================================
    res_bench = client.post("/api/optimization/benchmark", json=opt_req)
    assert res_bench.status_code == 200
    bench = res_bench.json()
    assert "ortools_metrics" in bench
    assert "highs_metrics" in bench
    assert "baseline_metrics" in bench
    assert bench["ortools_metrics"]["service_level_percent"] == 100.0
    assert bench["highs_metrics"]["service_level_percent"] == 100.0

    # =========================================================================
    # Step 7: Inspect Decision Receipts and export the plan
    # =========================================================================
    run_id = plan["run_id"]
    res_receipts = client.get(f"/api/optimization/runs/{run_id}/receipts")
    assert res_receipts.status_code == 200
    receipts = res_receipts.json()
    assert len(receipts) > 0
    rec = receipts[0]
    assert rec["currency"] == "INR"
    assert "evidence" in rec
    assert rec["source_location_id"] == "LOC-DEL-RDC"

    res_export = client.get(f"/api/optimization/runs/{run_id}/export")
    assert res_export.status_code == 200
    assert "text/csv" in res_export.headers.get("content-type", "")
    assert "shipment_id,planning_run_id" in res_export.text

    # =========================================================================
    # Step 8: Approve a shipment after revalidating stock
    # =========================================================================
    rec_shipment = plan["recommended_shipments"][0]
    shp_id = rec_shipment["shipment_id"]

    res_appr = client.post(
        f"/api/shipments/{shp_id}/approve",
        json={"approved": True, "authorized_user_id": "USER-PLANNER-01", "notes": "Approved for priority dispatch"},
    )
    assert res_appr.status_code == 200
    appr_data = res_appr.json()
    assert appr_data["approval_status"] == "approved"
    assert appr_data["status"] == "approved"

    # =========================================================================
    # Step 9: Prepare dispatch and reserve inventory
    # =========================================================================
    res_prep = client.post(
        f"/api/shipments/{shp_id}/prepare",
        json={
            "authorized_user_id": "USER-SUP-01",
            "actor_role": "dock_supervisor",
            "checklist_items": ["packaging_inspected", "quantity_reconciled"],
            "notes": "Staged at Bay 4",
        },
    )
    assert res_prep.status_code == 200
    prep_data = res_prep.json()
    assert prep_data["status"] == "ready_for_dispatch"

    # Verify origin inventory was reserved
    inv_origin = client.get("/api/inventory?location_id=LOC-DEL-RDC&sku_id=SKU-GHEE-1L").json()[0]
    assert inv_origin["reserved"] >= rec_shipment["quantity"]

    # =========================================================================
    # Step 10: Record physical dispatch
    # =========================================================================
    res_disp = client.post(
        f"/api/shipments/{shp_id}/dispatch",
        json={
            "authorized_user_id": "USER-MGR-01",
            "actor_role": "dispatch_manager",
            "consignment_number": "WAYBILL-AMUL-9901",
            "vehicle_number": "DL-01-AB-1234",
            "driver_contact": "Ramesh (+91 98765 43210)",
        },
    )
    assert res_disp.status_code == 200
    disp_data = res_disp.json()
    assert disp_data["status"] == "in_transit"

    # Verify physical on_hand and reserved decreased at origin
    inv_origin_after = client.get("/api/inventory?location_id=LOC-DEL-RDC&sku_id=SKU-GHEE-1L").json()[0]
    assert inv_origin_after["on_hand"] == inv_origin["on_hand"] - rec_shipment["quantity"]
    assert inv_origin_after["reserved"] == inv_origin["reserved"] - rec_shipment["quantity"]

    # =========================================================================
    # Step 11: Confirm delivery and reconcile destination inventory
    # =========================================================================
    inv_dest_before = client.get("/api/inventory?location_id=LOC-DEL-DIST&sku_id=SKU-GHEE-1L").json()[0]

    res_deliv = client.post(
        f"/api/shipments/{shp_id}/deliver",
        json={
            "authorized_user_id": "USER-REC-01",
            "actor_role": "receiving_officer",
            "actual_transport_cost": 450.0,
            "pod_reference": "POD-SIGNED-9901",
            "notes": "Inspected all cartons intact with seals verified",
        },
    )
    assert res_deliv.status_code == 200
    deliv_data = res_deliv.json()
    assert deliv_data["status"] == "delivered"
    assert deliv_data["pod_reference"] == "POD-SIGNED-9901"
    assert deliv_data["actual_transport_cost"] == 450.0

    # Verify destination on_hand reconciled
    inv_dest_after = client.get("/api/inventory?location_id=LOC-DEL-DIST&sku_id=SKU-GHEE-1L").json()[0]
    assert inv_dest_after["on_hand"] == inv_dest_before["on_hand"] + rec_shipment["quantity"]

    # =========================================================================
    # Step 12: Verify shipment audit history
    # =========================================================================
    res_events = client.get(f"/api/shipments/{shp_id}/events")
    assert res_events.status_code == 200
    events = res_events.json()
    assert len(events) >= 4
    statuses = [e["to_status"] for e in events]
    assert "approved" in statuses
    assert "ready_for_dispatch" in statuses
    assert "in_transit" in statuses
    assert "delivered" in statuses

    # =========================================================================
    # Step 13: Confirm unauthorized users cannot perform restricted actions
    # =========================================================================
    # A read-only viewer trying to trigger optimization gets 403 Forbidden
    res_unauth_opt = client.post(
        "/api/optimization/run",
        json=opt_req,
        headers={"X-StockWise-Role": "viewer", "Authorization": "Bearer demo-viewer-token"},
    )
    assert res_unauth_opt.status_code == 403

    # A read-only viewer trying to approve a shipment gets 403 Forbidden
    res_unauth_appr = client.post(
        f"/api/shipments/{shp_id}/approve",
        json={"approved": True, "authorized_user_id": "USER-VIEWER-01"},
        headers={"X-StockWise-Role": "viewer", "Authorization": "Bearer demo-viewer-token"},
    )
    assert res_unauth_appr.status_code == 403

    # A planner trying to dispatch (requires logistics role or admin) gets 403 Forbidden
    res_planner_disp = client.post(
        f"/api/shipments/{shp_id}/dispatch",
        json={"authorized_user_id": "USER-PLANNER-01"},
        headers={"X-StockWise-Role": "planner", "Authorization": "Bearer demo-planner-token"},
    )
    assert res_planner_disp.status_code == 403

    # =========================================================================
    # Step 14: Confirm all three portals remain functional
    # =========================================================================
    # Portal 1: Company Admin Portal
    assert client.get("/api/organizations").status_code == 200
    assert client.get("/api/network/locations").status_code == 200
    assert client.get("/api/network/routes").status_code == 200
    assert client.get("/api/imports").status_code == 200

    # Portal 2: Distribution Intelligence Portal
    assert client.get("/api/network/eligibility").status_code == 200
    assert client.get("/api/inventory").status_code == 200
    assert client.get("/api/products").status_code == 200
    assert client.get("/api/forecast?horizon_days=7").status_code == 200
    assert client.get("/api/inventory-risk?horizon_days=7").status_code == 200

    # Portal 3: Warehouse & Logistics Portal
    assert client.get("/api/shipments").status_code == 200
    assert client.get("/api/shipments/movements").status_code == 200
    assert client.get(f"/api/shipments/{shp_id}/traceability").status_code == 200


def test_idempotency_replay_protection(client: TestClient):
    """
    Verifies that requests replayed with the same Idempotency-Key
    return cached responses without executing duplicate mutations.
    """
    # Propose a new shipment
    client.post("/api/network/locations", json={"location_id": "LOC-A", "name": "Warehouse Alpha", "location_type": "company_warehouse", "region": "North"})
    client.post("/api/network/locations", json={"location_id": "LOC-B", "name": "Warehouse Beta", "location_type": "company_warehouse", "region": "North"})
    client.post("/api/network/routes", json={"from_location_id": "LOC-A", "to_location_id": "LOC-B", "lead_time_days": 1.0, "cost_rate": 2.0, "is_active": True})
    client.post("/api/imports/products", files={"file": ("p.csv", io.BytesIO(b"sku_id,name,category,unit,case_pack,shelf_life_days\nSKU-IDEMP,Item,Cat,cases,10,100\n"), "text/csv")})
    client.post("/api/imports/inventory", files={"file": ("i.csv", io.BytesIO(b"snapshot_id,sku_id,location_id,on_hand,reserved,blocked,confirmed_incoming,as_of_date\nSNAP,SKU-IDEMP,LOC-A,1000,0,0,0,2026-10-24\n"), "text/csv")})

    prop = client.post(
        "/api/shipments/propose",
        json={"sku_id": "SKU-IDEMP", "source_location_id": "LOC-A", "destination_location_id": "LOC-B", "quantity": 100},
    ).json()
    shp_id = prop["shipment_id"]

    idempotency_key = "idemp-test-approval-key-12345"

    # First Approval
    res1 = client.post(
        f"/api/shipments/{shp_id}/approve",
        json={"approved": True, "authorized_user_id": "USER-PLANNER-01", "notes": "First approval call"},
        headers={"Idempotency-Key": idempotency_key},
    )
    assert res1.status_code == 200
    data1 = res1.json()

    # Replay with identical payload & key
    res2 = client.post(
        f"/api/shipments/{shp_id}/approve",
        json={"approved": True, "authorized_user_id": "USER-PLANNER-01", "notes": "First approval call"},
        headers={"Idempotency-Key": idempotency_key},
    )
    assert res2.status_code == 200
    data2 = res2.json()

    # Verify both responses match exactly
    assert data1["shipment_id"] == data2["shipment_id"]
    assert data1["status"] == data2["status"]
    assert data1["approval_status"] == data2["approval_status"]

    # Verify movements count is NOT duplicated
    movements = client.get(f"/api/shipments/movements?shipment_id={shp_id}").json()
    approved_movements = [m for m in movements if m["movement_type"] == "approved_allocation"]
    assert len(approved_movements) == 1


def test_system_readiness_probe(client: TestClient):
    """
    Verifies /api/ready probe checks database pool, query execution latency,
    and returns healthy status.
    """
    res = client.get("/api/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert "latency_ms" in data
    assert data["service"] == settings.APP_NAME
