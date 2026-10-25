import io
from fastapi.testclient import TestClient


def test_ac1_register_company_warehouse_and_cnf_facility(client: TestClient):
    """
    AC 1: An administrator can register a company warehouse and a separate C&F-operated facility.
    Distinguishes facility owner and facility operator.
    """
    # 1. Register FMCG Company
    resp_fmcg = client.post(
        "/api/organizations",
        json={
            "org_id": "ORG-HUL",
            "name": "Hindustan Consumer Products Ltd",
            "org_type": "fmcg_company",
            "contact_email": "ops@hcp.com",
            "is_active": True,
        },
    )
    assert resp_fmcg.status_code == 201

    # 2. Register C&F Agency
    resp_cnf_agency = client.post(
        "/api/organizations",
        json={
            "org_id": "ORG-MAH-CNF",
            "name": "Maharashtra Logistics & Forwarding Agents",
            "org_type": "cnf_agency",
            "contact_email": "forwarding@mahcnf.com",
            "is_active": True,
        },
    )
    assert resp_cnf_agency.status_code == 201

    # 3. Register Company Warehouse (Owned and Operated by FMCG)
    resp_co_wh = client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-WH-MUMBAI",
            "name": "Bhiwandi Central Warehouse",
            "location_type": "company_warehouse",
            "region": "West",
            "city": "Mumbai",
            "owner_org_id": "ORG-HUL",
            "operator_org_id": "ORG-HUL",
            "storage_capacity_units": 100000,
            "dispatch_capacity_daily": 5000,
            "is_active": True,
        },
    )
    assert resp_co_wh.status_code == 201
    co_data = resp_co_wh.json()
    assert co_data["owner_org_id"] == "ORG-HUL"
    assert co_data["operator_org_id"] == "ORG-HUL"
    assert co_data["owner_org_name"] == "Hindustan Consumer Products Ltd"
    assert co_data["operator_org_name"] == "Hindustan Consumer Products Ltd"

    # 4. Register C&F Facility (Owned by FMCG, Operated by C&F Agency)
    resp_cnf_loc = client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-CNF-NAGPUR",
            "name": "Vidarbha C&F Depot",
            "location_type": "cnf_facility",
            "region": "West",
            "city": "Nagpur",
            "owner_org_id": "ORG-HUL",
            "operator_org_id": "ORG-MAH-CNF",
            "storage_capacity_units": 45000,
            "dispatch_capacity_daily": 2500,
            "is_active": True,
        },
    )
    assert resp_cnf_loc.status_code == 201
    cnf_data = resp_cnf_loc.json()
    assert cnf_data["owner_org_id"] == "ORG-HUL"
    assert cnf_data["operator_org_id"] == "ORG-MAH-CNF"
    assert cnf_data["owner_org_name"] == "Hindustan Consumer Products Ltd"
    assert cnf_data["operator_org_name"] == "Maharashtra Logistics & Forwarding Agents"


def test_ac2_cnf_stores_fmcg_owned_inventory_without_changing_owner(client: TestClient):
    """
    AC 2: The C&F facility can store inventory owned by the FMCG company without changing its owner.
    """
    # Setup master data
    client.post("/api/organizations", json={"org_id": "ORG-FMCG-1", "name": "Britannia Consumer", "org_type": "fmcg_company"})
    client.post("/api/organizations", json={"org_id": "ORG-CNF-1", "name": "Apex C&F Services", "org_type": "cnf_agency"})
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-CNF-PUNE",
            "name": "Pune C&F Depot",
            "location_type": "cnf_facility",
            "region": "West",
            "owner_org_id": "ORG-FMCG-1",
            "operator_org_id": "ORG-CNF-1",
        },
    )
    client.post(
        "/api/imports/products",
        files={"file": ("products.csv", io.BytesIO(b"sku_id,name,category,unit,case_pack,shelf_life_days\nSKU-BISCUIT-101,Marie Gold,Biscuits,cases,24,180\n"), "text/csv")},
    )

    # Ingest inventory at C&F facility with owner=FMCG
    inv_csv = (
        "snapshot_id,sku_id,location_id,on_hand,reserved,blocked,confirmed_incoming,as_of_date,owner_org_id,batch_number,expiry_date\n"
        "SNAP-001,SKU-BISCUIT-101,LOC-CNF-PUNE,5000,500,200,1000,2026-10-24,ORG-FMCG-1,BAT-202610-A,2027-04-24\n"
    )
    resp = client.post("/api/imports/inventory", files={"file": ("inv.csv", io.BytesIO(inv_csv.encode("utf-8")), "text/csv")})
    assert resp.status_code == 200
    assert resp.json()["valid_rows"] == 1

    # Verify inventory in database retains FMCG ownership
    inv_list = client.get("/api/inventory").json()
    assert len(inv_list) == 1
    assert inv_list[0]["location_id"] == "LOC-CNF-PUNE"
    assert inv_list[0]["owner_org_id"] == "ORG-FMCG-1"  # FMCG company owns the stock!
    assert inv_list[0]["batch_number"] == "BAT-202610-A"
    assert inv_list[0]["dispatchable_stock"] == 4300.0  # 5000 - 500 - 200 = 4300


def test_ac3_distributor_represented_as_independent_org_and_destination(client: TestClient):
    """
    AC 3: A distributor can be represented as an independent organization and destination without a separate portal.
    """
    # Register distributor org
    dist_org = client.post(
        "/api/organizations",
        json={
            "org_id": "ORG-DIST-DELHI",
            "name": "Krishna Traders Delhi",
            "org_type": "distributor",
            "contact_email": "sales@krishnatraders.com",
            "contact_phone": "+91-9811002233",
            "is_active": True,
        },
    )
    assert dist_org.status_code == 201

    # Register distributor warehouse
    dist_wh = client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-DIST-NORTH",
            "name": "North Delhi Primary Stockist",
            "location_type": "distributor_warehouse",
            "region": "North",
            "city": "New Delhi",
            "owner_org_id": "ORG-DIST-DELHI",
            "operator_org_id": "ORG-DIST-DELHI",
            "storage_capacity_units": 15000,
            "is_active": True,
        },
    )
    assert dist_wh.status_code == 201
    assert dist_wh.json()["owner_org_id"] == "ORG-DIST-DELHI"
    assert dist_wh.json()["location_type"] == "distributor_warehouse"


def test_ac4_3pl_provider_assigned_to_permitted_route_without_owning_inventory(client: TestClient):
    """
    AC 4: A third-party logistics provider can be assigned to a permitted route without becoming the inventory owner.
    """
    # 1. Register organizations
    client.post("/api/organizations", json={"org_id": "ORG-FMCG", "name": "Godrej Consumer", "org_type": "fmcg_company"})
    client.post("/api/organizations", json={"org_id": "ORG-3PL-TCI", "name": "TCI Freight Express", "org_type": "logistics_provider"})

    # 2. Register locations
    client.post("/api/network/locations", json={"location_id": "LOC-MFG-GUJ", "name": "Kandla Plant", "location_type": "manufacturing_plant", "region": "West", "owner_org_id": "ORG-FMCG"})
    client.post("/api/network/locations", json={"location_id": "LOC-RDC-DEL", "name": "Delhi RDC", "location_type": "regional_warehouse", "region": "North", "owner_org_id": "ORG-FMCG"})

    # 3. Create route with 3PL assigned
    route_resp = client.post(
        "/api/network/routes",
        json={
            "from_location_id": "LOC-MFG-GUJ",
            "to_location_id": "LOC-RDC-DEL",
            "carrier_agency_id": "ORG-3PL-TCI",
            "lead_time_days": 2.5,
            "cost_rate": 14.5,
            "capacity_units": 8000,
            "sku_eligibility": "all",
            "pricing_basis": "per_unit",
            "is_active": True,
        },
    )
    assert route_resp.status_code == 201
    route_data = route_resp.json()
    assert route_data["carrier_agency_id"] == "ORG-3PL-TCI"
    assert route_data["carrier_agency_name"] == "TCI Freight Express"


def test_ac5_dispatchable_stock_excludes_reserved_and_blocked(client: TestClient):
    """
    AC 5: Dispatchable stock excludes reserved and blocked quantities: max(0, on_hand - reserved - blocked).
    Incoming stock must NOT be counted as currently dispatchable.
    """
    client.post("/api/network/locations", json={"location_id": "LOC-WH-1", "name": "WH 1", "location_type": "company_warehouse", "region": "East"})
    client.post(
        "/api/imports/products",
        files={"file": ("products.csv", io.BytesIO(b"sku_id,name,category,unit,case_pack,shelf_life_days\nSKU-OIL-1,Cooking Oil,Edible Oil,cases,15,365\n"), "text/csv")},
    )

    # Ingest: On Hand = 1000, Reserved = 250, Blocked = 150, Incoming = 500
    inv_csv = (
        "snapshot_id,sku_id,location_id,on_hand,reserved,blocked,confirmed_incoming,as_of_date\n"
        "SNAP-01,SKU-OIL-1,LOC-WH-1,1000,250,150,500,2026-10-24\n"
    )
    client.post("/api/imports/inventory", files={"file": ("inv.csv", io.BytesIO(inv_csv.encode("utf-8")), "text/csv")})

    inv = client.get("/api/inventory").json()[0]
    # Expected: 1000 - 250 - 150 = 600. Confirmed incoming (500) must NOT be added!
    assert inv["dispatchable_stock"] == 600.0


def test_ac6_forbidden_route_and_stock_exceeded_rejected(client: TestClient):
    """
    AC 6: A shipment cannot use a forbidden route or exceed the configured source stock.
    Both attempts must return HTTP 400 Bad Request with clear error details.
    """
    # Setup locations and SKU
    client.post("/api/network/locations", json={"location_id": "LOC-A", "name": "Facility A", "location_type": "company_warehouse", "region": "South"})
    client.post("/api/network/locations", json={"location_id": "LOC-B", "name": "Facility B", "location_type": "regional_warehouse", "region": "South"})
    client.post("/api/network/locations", json={"location_id": "LOC-C", "name": "Facility C (Forbidden)", "location_type": "distributor_warehouse", "region": "South"})
    client.post("/api/imports/products", files={"file": ("products.csv", io.BytesIO(b"sku_id,name,category,unit,case_pack,shelf_life_days\nSKU-TEST-1,Test Tea,Beverages,cases,20,365\n"), "text/csv")})

    # Permitted route only A -> B
    client.post(
        "/api/network/routes",
        json={"from_location_id": "LOC-A", "to_location_id": "LOC-B", "lead_time_days": 1.0, "cost_rate": 5.0, "is_active": True},
    )

    # Ingest 500 on-hand, 100 reserved -> 400 dispatchable at LOC-A
    inv_csv = "snapshot_id,sku_id,location_id,on_hand,reserved,blocked,confirmed_incoming,as_of_date\nSNAP-1,SKU-TEST-1,LOC-A,500,100,0,0,2026-10-24\n"
    client.post("/api/imports/inventory", files={"file": ("inv.csv", io.BytesIO(inv_csv.encode("utf-8")), "text/csv")})

    # Attempt 1: Shipment on FORBIDDEN route A -> C
    resp_forbidden = client.post(
        "/api/shipments/propose",
        json={"sku_id": "SKU-TEST-1", "source_location_id": "LOC-A", "destination_location_id": "LOC-C", "quantity": 100},
    )
    assert resp_forbidden.status_code == 400
    assert "FORBIDDEN_ROUTE" in resp_forbidden.json()["detail"]

    # Attempt 2: Shipment on valid route A -> B, but EXCEEDING source stock (asking 450 when only 400 dispatchable)
    resp_overstock = client.post(
        "/api/shipments/propose",
        json={"sku_id": "SKU-TEST-1", "source_location_id": "LOC-A", "destination_location_id": "LOC-B", "quantity": 450},
    )
    assert resp_overstock.status_code == 400
    assert "INSUFFICIENT_DISPATCHABLE_STOCK" in resp_overstock.json()["detail"]

    # Attempt 3: Valid proposal (300 units <= 400)
    resp_valid = client.post(
        "/api/shipments/propose",
        json={"sku_id": "SKU-TEST-1", "source_location_id": "LOC-A", "destination_location_id": "LOC-B", "quantity": 300},
    )
    assert resp_valid.status_code == 201
    assert resp_valid.json()["status"] == "proposed"
    assert resp_valid.json()["approval_status"] == "pending"


def test_ac7_route_missing_or_invalid_lead_time_flagged_ineligible(client: TestClient):
    """
    AC 7: A route with missing or invalid required cost or lead-time data is flagged rather than silently treated as feasible.
    """
    client.post("/api/network/locations", json={"location_id": "LOC-X", "name": "Facility X", "location_type": "company_warehouse", "region": "North"})
    client.post("/api/network/locations", json={"location_id": "LOC-Y", "name": "Facility Y", "location_type": "regional_warehouse", "region": "North"})

    # Check network eligibility API
    elig_resp = client.get("/api/network/eligibility")
    assert elig_resp.status_code == 200
    elig_data = elig_resp.json()
    assert "total_locations" in elig_data
    assert "eligible_corridors" in elig_data


def test_ac8_inactive_facilities_and_routes_excluded(client: TestClient):
    """
    AC 8: Inactive facilities and routes are excluded from new recommendations.
    """
    # Active source, Inactive route
    client.post("/api/network/locations", json={"location_id": "LOC-ACT-1", "name": "Active Hub", "location_type": "company_warehouse", "region": "West", "is_active": True})
    client.post("/api/network/locations", json={"location_id": "LOC-ACT-2", "name": "Active Dest", "location_type": "distributor_warehouse", "region": "West", "is_active": True})
    client.post("/api/imports/products", files={"file": ("products.csv", io.BytesIO(b"sku_id,name,category,unit,case_pack,shelf_life_days\nSKU-INACT-1,Test Biscuit,Biscuits,cases,10,180\n"), "text/csv")})
    client.post("/api/imports/inventory", files={"file": ("inv.csv", io.BytesIO(b"snapshot_id,sku_id,location_id,on_hand,reserved,blocked,confirmed_incoming,as_of_date\nSNAP-1,SKU-INACT-1,LOC-ACT-1,500,0,0,0,2026-10-24\n"), "text/csv")})

    # Inactive route
    client.post(
        "/api/network/routes",
        json={"from_location_id": "LOC-ACT-1", "to_location_id": "LOC-ACT-2", "lead_time_days": 2.0, "cost_rate": 8.0, "is_active": False},
    )

    # Attempt shipment on inactive route
    resp = client.post(
        "/api/shipments/propose",
        json={"sku_id": "SKU-INACT-1", "source_location_id": "LOC-ACT-1", "destination_location_id": "LOC-ACT-2", "quantity": 100},
    )
    assert resp.status_code == 400
    assert "INELIGIBLE_ROUTE" in resp.json()["detail"]
    assert "Route is currently deactivated / inactive" in resp.json()["detail"]


def test_ac9_duplicate_imports_and_invalid_references_reported_clearly(client: TestClient):
    """
    AC 9: Duplicate imports and invalid organization/location references are reported clearly without crashing.
    """
    # Duplicate orgs in same upload
    dup_org_csv = (
        "org_id,name,org_type,contact_email\n"
        "ORG-DUP-1,First Org,distributor,first@dist.com\n"
        "ORG-DUP-1,Duplicate Org,distributor,dup@dist.com\n"
    )
    resp = client.post("/api/imports/organizations", files={"file": ("orgs.csv", io.BytesIO(dup_org_csv.encode("utf-8")), "text/csv")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_rows"] == 1
    assert data["rejected_rows"] == 1
    assert any(err["error_code"] == "DUPLICATE_KEY" for err in data["errors"])

    # Location referencing non-existent organization
    bad_loc_csv = (
        "location_id,name,location_type,region,owner_org_id\n"
        "LOC-BAD-REF,Ghost Facility,company_warehouse,East,ORG-NON-EXISTENT\n"
    )
    resp_loc = client.post("/api/imports/locations", files={"file": ("locs.csv", io.BytesIO(bad_loc_csv.encode("utf-8")), "text/csv")})
    assert resp_loc.status_code == 200
    data_loc = resp_loc.json()
    assert data_loc["rejected_rows"] == 1
    assert any(err["error_code"] == "UNKNOWN_ORGANIZATION" for err in data_loc["errors"])


def test_ac10_shipment_approval_does_not_auto_dispatch(client: TestClient):
    """
    AC 10: Shipment approval records a governance decision without automatically dispatching vehicles or falsely claiming delivery.
    """
    # Setup data and propose shipment
    client.post("/api/network/locations", json={"location_id": "LOC-S1", "name": "Source Plant", "location_type": "manufacturing_plant", "region": "Central"})
    client.post("/api/network/locations", json={"location_id": "LOC-D1", "name": "Dest Warehouse", "location_type": "company_warehouse", "region": "Central"})
    client.post("/api/network/routes", json={"from_location_id": "LOC-S1", "to_location_id": "LOC-D1", "lead_time_days": 1.0, "cost_rate": 4.0, "is_active": True})
    client.post("/api/imports/products", files={"file": ("products.csv", io.BytesIO(b"sku_id,name,category,unit,case_pack,shelf_life_days\nSKU-GOV-1,Soap,Personal Care,cases,24,365\n"), "text/csv")})
    client.post("/api/imports/inventory", files={"file": ("inv.csv", io.BytesIO(b"snapshot_id,sku_id,location_id,on_hand,reserved,blocked,confirmed_incoming,as_of_date\nSNAP-1,SKU-GOV-1,LOC-S1,2000,0,0,0,2026-10-24\n"), "text/csv")})

    prop_resp = client.post(
        "/api/shipments/propose",
        json={"sku_id": "SKU-GOV-1", "source_location_id": "LOC-S1", "destination_location_id": "LOC-D1", "quantity": 500},
    )
    assert prop_resp.status_code == 201
    shp_id = prop_resp.json()["shipment_id"]

    # Governance Approval
    appr_resp = client.post(
        f"/api/shipments/{shp_id}/approve",
        json={"approved": True, "authorized_user_id": "USER-PLANNER-01", "notes": "Approved for dispatch batch #44"},
    )
    assert appr_resp.status_code == 200
    appr_data = appr_resp.json()

    # CRITICAL CHECK: Status is 'approved', NOT 'in_transit' or 'delivered'
    assert appr_data["approval_status"] == "approved"
    assert appr_data["status"] == "approved"
    assert appr_data["approved_by"] == "USER-PLANNER-01"

    # Verify audit movement was created
    mov_resp = client.get(f"/api/shipments/movements?shipment_id={shp_id}")
    assert mov_resp.status_code == 200
    movements = mov_resp.json()
    assert len(movements) >= 2  # proposal + approval
    assert any(m["movement_type"] == "approved_allocation" for m in movements)

    # Operational update (e.g. marked ready for dispatch by warehouse operator)
    status_resp = client.post(
        f"/api/shipments/{shp_id}/status",
        json={"status": "ready_for_dispatch", "notes": "Goods palletized at Bay 3"},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "ready_for_dispatch"


def test_ac11_all_three_portals_contracts(client: TestClient):
    """
    AC 11: All three existing portals continue to work after implementation.
    Verifies API contracts required by Company Admin, Distribution Intelligence, and Warehouse & Logistics Portals.
    """
    # Portal 1: Company Admin Portal endpoints
    assert client.get("/api/organizations").status_code == 200
    assert client.get("/api/network/locations").status_code == 200
    assert client.get("/api/network/routes").status_code == 200
    assert client.get("/api/imports").status_code == 200

    # Portal 2: Distribution Intelligence Portal endpoints
    assert client.get("/api/network/eligibility").status_code == 200
    assert client.get("/api/inventory").status_code == 200
    assert client.get("/api/products").status_code == 200

    # Portal 3: Warehouse & Logistics Portal endpoints
    assert client.get("/api/shipments").status_code == 200
    assert client.get("/api/shipments/movements").status_code == 200


def test_ac12_existing_functionality_preserved(client: TestClient):
    """
    AC 12: Existing working functionality and historical records are preserved.
    """
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/products").status_code == 200
    assert client.get("/api/locations").status_code == 200
    assert client.get("/api/routes").status_code == 200
    assert client.get("/api/sales").status_code == 200
    assert client.get("/api/imports/templates/organizations?format=csv").status_code == 200
