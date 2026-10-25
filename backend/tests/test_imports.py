import io
import os
from fastapi.testclient import TestClient
import openpyxl


def test_download_csv_template(client: TestClient):
    """Test downloading CSV templates for all dataset types."""
    for dt in ["products", "locations", "inventory", "sales", "routes"]:
        response = client.get(f"/api/imports/templates/{dt}?format=csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert len(response.text) > 0


def test_download_excel_template(client: TestClient):
    """Test downloading Excel templates."""
    response = client.get("/api/imports/templates/products?format=xlsx")
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert len(response.content) > 0


def test_valid_products_csv_import(client: TestClient):
    """Test uploading a valid products CSV file."""
    csv_data = (
        "sku_id,name,category,unit,case_pack,shelf_life_days\n"
        "SKU-001,Detergent Powder,Fabric Care,cases,12,730\n"
        "SKU-002,Bathing Soap,Personal Care,cases,24,365\n"
    )
    files = {"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/products", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_rows"] == 2
    assert data["valid_rows"] == 2
    assert data["rejected_rows"] == 0
    assert len(data["errors"]) == 0

    # Verify persistence in /api/products
    prod_resp = client.get("/api/products")
    assert prod_resp.status_code == 200
    products = prod_resp.json()
    assert len(products) == 2
    assert products[0]["sku_id"] == "SKU-001"


def test_valid_products_excel_import(client: TestClient):
    """Test uploading a valid products Excel file (.xlsx)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["sku_id", "name", "category", "unit", "case_pack", "shelf_life_days"])
    ws.append(["SKU-EXCEL-1", "Excel Product 1", "Groceries", "cases", 10, 180])
    excel_stream = io.BytesIO()
    wb.save(excel_stream)
    excel_stream.seek(0)

    files = {"file": ("products.xlsx", excel_stream, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    response = client.post("/api/imports/products", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["valid_rows"] == 1
    assert data["rejected_rows"] == 0


def test_products_missing_required_fields(client: TestClient):
    """Test rejection when required fields are missing."""
    csv_data = (
        "sku_id,name,category,unit,case_pack\n"
        ",Detergent Without SKU,Fabric Care,cases,12\n"
        "SKU-VALID,Named Product,Fabric Care,cases,12\n"
    )
    files = {"file": ("products_missing.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/products", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert data["valid_rows"] == 1
    assert data["rejected_rows"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["error_code"] == "MISSING_FIELD"
    assert data["errors"][0]["field_name"] == "sku_id"


def test_products_duplicate_key_rejection(client: TestClient):
    """Test rejection of duplicate keys within the uploaded file."""
    csv_data = (
        "sku_id,name,category,unit,case_pack\n"
        "SKU-DUP,Product A,Fabric Care,cases,12\n"
        "SKU-DUP,Product B,Fabric Care,cases,12\n"
    )
    files = {"file": ("products_dup.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/products", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert data["valid_rows"] == 1
    assert data["rejected_rows"] == 1
    assert data["errors"][0]["error_code"] == "DUPLICATE_KEY"


def test_valid_locations_csv_import_seven_sample_records(client: TestClient):
    """Test uploading valid Locations CSV with all 7 sample locations."""
    csv_data = (
        "location_id,name,location_type,region,city,address,storage_capacity_units,dispatch_capacity_daily,is_active\n"
        "LOC-PLT-NAS,Nashik Manufacturing Plant,manufacturing_plant,West,Nashik,Ambad MIDC Industrial Area,50000,12000,True\n"
        "LOC-WH-MUM,Mumbai Central Warehouse,company_warehouse,West,Mumbai,Plot 12 MIDC Industrial Area,30000,8000,True\n"
        "LOC-RDC-PUN,Pune Regional Distribution Centre,regional_warehouse,West,Pune,Chakan MIDC Phase 2,18000,5000,True\n"
        "LOC-DC-PUN,Pune Distributor Godown,distributor_warehouse,West,Pune,Wagholi Logistics Park,6000,1800,True\n"
        "LOC-DC-KOL,Kolhapur Distributor Godown,distributor_warehouse,West,Kolhapur,Shiroli MIDC Industrial Area,4500,1200,True\n"
        "LOC-RET-NAS01,Nashik Retail Store 01,retail_destination,West,Nashik,College Road Retail Market,1200,250,True\n"
        "LOC-RET-PUN01,Pune Retail Store 01,retail_destination,West,Pune,FC Road Commercial Hub,1000,200,True\n"
    )
    files = {"file": ("locations.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/locations", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_rows"] == 7
    assert data["valid_rows"] == 7
    assert data["rejected_rows"] == 0
    assert len(data["errors"]) == 0

    # Verify retrieval from /api/locations
    loc_resp = client.get("/api/locations")
    assert loc_resp.status_code == 200
    locs = loc_resp.json()
    assert len(locs) >= 7
    assert any(l["location_id"] == "LOC-PLT-NAS" and l["region"] == "West" for l in locs)

    # Verify retrieval from /api/network/locations
    net_resp = client.get("/api/network/locations")
    assert net_resp.status_code == 200
    net_locs = net_resp.json()
    nas_plant = next((l for l in net_locs if l["location_id"] == "LOC-PLT-NAS"), None)
    assert nas_plant is not None
    assert nas_plant["region"] == "West"
    assert nas_plant["storage_capacity_units"] == 50000.0


def test_valid_locations_excel_import(client: TestClient):
    """Test uploading valid Locations Excel (.xlsx) file with all 7 sample locations."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "locations"
    ws.append(["location_id", "name", "location_type", "region", "city", "address", "storage_capacity_units", "dispatch_capacity_daily", "is_active"])
    rows = [
        ["LOC-PLT-NAS", "Nashik Manufacturing Plant", "plant", "West", "Nashik", "Ambad MIDC", 50000, 12000, True],
        ["LOC-WH-MUM", "Mumbai Central Warehouse", "company_warehouse", "West", "Mumbai", "Plot 12 MIDC", 30000, 8000, True],
        ["LOC-RDC-PUN", "Pune Regional Distribution Centre", "regional_warehouse", "West", "Pune", "Chakan MIDC", 18000, 5000, True],
        ["LOC-DC-PUN", "Pune Distributor Godown", "distributor", "West", "Pune", "Wagholi Park", 6000, 1800, True],
        ["LOC-DC-KOL", "Kolhapur Distributor Godown", "distributor", "West", "Kolhapur", "Shiroli MIDC", 4500, 1200, True],
        ["LOC-RET-NAS01", "Nashik Retail Store 01", "retailer", "West", "Nashik", "College Road", 1200, 250, True],
        ["LOC-RET-PUN01", "Pune Retail Store 01", "retailer", "West", "Pune", "FC Road", 1000, 200, True],
    ]
    for r in rows:
        ws.append(r)
    excel_stream = io.BytesIO()
    wb.save(excel_stream)
    excel_stream.seek(0)

    files = {"file": ("locations.xlsx", excel_stream, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    response = client.post("/api/imports/locations", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_rows"] == 7
    assert data["valid_rows"] == 7
    assert data["rejected_rows"] == 0


def test_locations_missing_region_column_rejects_and_prevents_persistence(client: TestClient):
    """Test that missing required 'region' column produces MISSING_COLUMN error and does not persist."""
    csv_data = (
        "location_id,name,location_type,city,state,storage_capacity_units,dispatch_capacity_daily,is_active\n"
        "LOC-PLT-NAS-FAIL,Nashik Manufacturing Plant,plant,Nashik,Maharashtra,50000,12000,True\n"
        "LOC-WH-MUM-FAIL,Mumbai Central Warehouse,company_warehouse,Mumbai,Maharashtra,30000,8000,True\n"
        "LOC-RDC-PUN-FAIL,Pune Regional Distribution Centre,regional_warehouse,Pune,Maharashtra,18000,5000,True\n"
        "LOC-DC-PUN-FAIL,Pune Distributor Godown,distributor,Pune,Maharashtra,6000,1800,True\n"
        "LOC-DC-KOL-FAIL,Kolhapur Distributor Godown,distributor,Kolhapur,Maharashtra,4500,1200,True\n"
        "LOC-RET-NAS01-FAIL,Nashik Retail Store 01,retailer,Nashik,Maharashtra,1200,250,True\n"
        "LOC-RET-PUN01-FAIL,Pune Retail Store 01,retailer,Pune,Maharashtra,1000,200,True\n"
    )
    files = {"file": ("locations.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/locations", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["total_rows"] == 7
    assert data["valid_rows"] == 0
    assert data["rejected_rows"] == 7
    assert len(data["errors"]) >= 1

    region_err = next((e for e in data["errors"] if e["field_name"] == "region"), None)
    assert region_err is not None
    assert region_err["error_code"] == "MISSING_COLUMN"
    assert "Missing required column 'region'" in region_err["error_reason"]
    assert "Expected canonical headers" in region_err["error_reason"]

    # Verify no records were persisted into /api/locations
    loc_resp = client.get("/api/locations")
    assert loc_resp.status_code == 200
    loc_ids = [l["location_id"] for l in loc_resp.json()]
    assert "LOC-PLT-NAS-FAIL" not in loc_ids
    assert "LOC-WH-MUM-FAIL" not in loc_ids


def test_locations_blank_region_row_quarantine(client: TestClient):
    """Test that a blank region rejects only the affected row when column is present."""
    csv_data = (
        "location_id,name,location_type,region\n"
        "LOC-QUAR-VALID,Valid Location,company_warehouse,West\n"
        "LOC-QUAR-INVALID,Invalid Blank Region,distributor,\n"
    )
    files = {"file": ("locations_partial.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/locations", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert data["total_rows"] == 2
    assert data["valid_rows"] == 1
    assert data["rejected_rows"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row_index"] == 3
    assert data["errors"][0]["field_name"] == "region"
    assert data["errors"][0]["error_code"] == "MISSING_FIELD"
    assert "Location region is required." in data["errors"][0]["error_reason"]

    # Verify only the valid row is persisted
    loc_resp = client.get("/api/locations")
    loc_ids = [l["location_id"] for l in loc_resp.json()]
    assert "LOC-QUAR-VALID" in loc_ids
    assert "LOC-QUAR-INVALID" not in loc_ids


def test_locations_duplicate_id_and_invalid_type_validation(client: TestClient):
    """Test rejection of duplicate location IDs and invalid location types."""
    csv_data = (
        "location_id,name,location_type,region\n"
        "LOC-DUP-UNIQUE,First Copy,central_warehouse,North\n"
        "LOC-DUP-UNIQUE,Second Copy,distributor,North\n"
        "LOC-BAD-TYPE,Bad Type Facility,invalid_type_xyz,South\n"
    )
    files = {"file": ("locations_invalid.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/locations", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert data["valid_rows"] == 1
    assert data["rejected_rows"] == 2
    error_codes = [e["error_code"] for e in data["errors"]]
    assert "DUPLICATE_KEY" in error_codes
    assert "INVALID_LOCATION_TYPE" in error_codes


def test_downloaded_location_templates_round_trip(client: TestClient):
    """Test that downloading the official location template and re-uploading succeeds cleanly."""
    # 1. Download CSV template
    csv_resp = client.get("/api/imports/templates/locations?format=csv")
    assert csv_resp.status_code == 200
    assert "region" in csv_resp.text

    # Re-upload the downloaded CSV
    files_csv = {"file": ("StockWise_template_locations.csv", io.BytesIO(csv_resp.text.encode("utf-8")), "text/csv")}
    upload_csv_resp = client.post("/api/imports/locations", files=files_csv)
    assert upload_csv_resp.status_code == 200
    assert upload_csv_resp.json()["status"] == "completed"
    assert upload_csv_resp.json()["valid_rows"] == 7
    assert upload_csv_resp.json()["rejected_rows"] == 0

    # 2. Download Excel template
    xlsx_resp = client.get("/api/imports/templates/locations?format=xlsx")
    assert xlsx_resp.status_code == 200

    # Re-upload the downloaded Excel
    files_xlsx = {"file": ("StockWise_template_locations.xlsx", io.BytesIO(xlsx_resp.content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    upload_xlsx_resp = client.post("/api/imports/locations", files=files_xlsx)
    assert upload_xlsx_resp.status_code == 200
    assert upload_xlsx_resp.json()["status"] == "completed"
    assert upload_xlsx_resp.json()["valid_rows"] == 7
    assert upload_xlsx_resp.json()["rejected_rows"] == 0


def test_test_data_location_files_import_successfully(client: TestClient):
    """Test that backend/test_data/locations.csv and locations.xlsx import with 100% validity."""
    backend_csv = os.path.join(os.path.dirname(__file__), "..", "test_data", "locations.csv")
    with open(backend_csv, "rb") as f:
        files = {"file": ("locations.csv", io.BytesIO(f.read()), "text/csv")}
    res = client.post("/api/imports/locations", files=files)
    assert res.status_code == 200
    assert res.json()["status"] == "completed"
    assert res.json()["valid_rows"] == 7
    assert res.json()["rejected_rows"] == 0

    backend_xlsx = os.path.join(os.path.dirname(__file__), "..", "test_data", "locations.xlsx")
    with open(backend_xlsx, "rb") as f:
        files = {"file": ("locations.xlsx", io.BytesIO(f.read()), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res_x = client.post("/api/imports/locations", files=files)
    assert res_x.status_code == 200
    assert res_x.json()["status"] == "completed"
    assert res_x.json()["valid_rows"] == 7
    assert res_x.json()["rejected_rows"] == 0


def test_inventory_foreign_key_validation(client: TestClient):
    """Test that inventory referencing non-existent SKU or location is rejected."""
    # Seed 1 valid location only
    loc_csv = "location_id,name,location_type,region\nWH-REAL,Real Warehouse,central_warehouse,North\n"
    client.post("/api/imports/locations", files={"file": ("loc.csv", io.BytesIO(loc_csv.encode("utf-8")), "text/csv")})

    # Upload inventory with unknown SKU and unknown location
    inv_csv = (
        "snapshot_id,sku_id,location_id,on_hand,reserved,blocked,as_of_date\n"
        "SNAP-1,SKU-GHOST,WH-REAL,100,10,0,2026-10-24\n"
        "SNAP-1,SKU-GHOST,LOC-GHOST,100,10,0,2026-10-24\n"
    )
    files = {"file": ("inv.csv", io.BytesIO(inv_csv.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/inventory", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["valid_rows"] == 0
    assert data["rejected_rows"] == 2
    error_codes = [e["error_code"] for e in data["errors"]]
    assert "UNKNOWN_SKU" in error_codes


def test_inventory_dispatchable_calculation(client: TestClient):
    """Test dispatchable stock calculation: max(0, on_hand - reserved - blocked)."""
    # Seed product and location
    prod_csv = "sku_id,name,unit,case_pack\nSKU-ITEM1,Item One,cases,1\n"
    loc_csv = "location_id,name,location_type,region\nLOC-WH1,Warehouse One,central_warehouse,West\n"
    client.post("/api/imports/products", files={"file": ("p.csv", io.BytesIO(prod_csv.encode("utf-8")), "text/csv")})
    client.post("/api/imports/locations", files={"file": ("l.csv", io.BytesIO(loc_csv.encode("utf-8")), "text/csv")})

    # Upload inventory: on_hand=100, reserved=25, blocked=15 -> dispatchable should be 60
    inv_csv = (
        "snapshot_id,sku_id,location_id,on_hand,reserved,blocked,as_of_date\n"
        "SNAP-TEST,SKU-ITEM1,LOC-WH1,100,25,15,2026-10-24\n"
    )
    files = {"file": ("inv.csv", io.BytesIO(inv_csv.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/inventory", files=files)
    assert response.status_code == 200
    assert response.json()["valid_rows"] == 1

    # Check /api/inventory
    inv_get = client.get("/api/inventory")
    assert inv_get.status_code == 200
    items = inv_get.json()
    assert len(items) == 1
    assert items[0]["on_hand"] == 100.0
    assert items[0]["reserved"] == 25.0
    assert items[0]["blocked"] == 15.0
    assert items[0]["dispatchable_stock"] == 60.0


def test_inventory_negative_quantity_rejection(client: TestClient):
    """Test that negative on_hand or reserved quantities are rejected."""
    prod_csv = "sku_id,name,unit,case_pack\nSKU-P1,P1,cases,1\n"
    loc_csv = "location_id,name,location_type,region\nLOC-L1,L1,central_warehouse,West\n"
    client.post("/api/imports/products", files={"file": ("p.csv", io.BytesIO(prod_csv.encode("utf-8")), "text/csv")})
    client.post("/api/imports/locations", files={"file": ("l.csv", io.BytesIO(loc_csv.encode("utf-8")), "text/csv")})

    inv_csv = (
        "snapshot_id,sku_id,location_id,on_hand,reserved,blocked,as_of_date\n"
        "SNAP-TEST,SKU-P1,LOC-L1,-50,0,0,2026-10-24\n"
    )
    files = {"file": ("inv_neg.csv", io.BytesIO(inv_csv.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/inventory", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["rejected_rows"] == 1
    assert data["errors"][0]["error_code"] == "NEGATIVE_QUANTITY"


def test_routes_self_referencing_and_values(client: TestClient):
    """Test self-referencing route rejection and negative lead times."""
    loc_csv = "location_id,name,location_type,region\nLOC-A,Node A,regional_dc,North\nLOC-B,Node B,distributor,North\n"
    client.post("/api/imports/locations", files={"file": ("l.csv", io.BytesIO(loc_csv.encode("utf-8")), "text/csv")})

    # Route with from_id == to_id and route with negative lead time
    routes_csv = (
        "from_location_id,to_location_id,lead_time_days,cost_rate\n"
        "LOC-A,LOC-A,2.0,50.0\n"
        "LOC-A,LOC-B,-1.0,40.0\n"
        "LOC-B,LOC-A,1.5,35.0\n"
    )
    files = {"file": ("routes.csv", io.BytesIO(routes_csv.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/routes", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["valid_rows"] == 1  # only row 3 is valid
    assert data["rejected_rows"] == 2
    error_codes = [e["error_code"] for e in data["errors"]]
    assert "SELF_REFERENCING_ROUTE" in error_codes
    assert "NEGATIVE_QUANTITY" in error_codes or "INVALID_LEAD_TIME" in error_codes


def test_unsupported_file_extension(client: TestClient):
    """Test rejection of unsupported file types."""
    files = {"file": ("data.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}
    response = client.post("/api/imports/products", files=files)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_import_history_and_errors_api(client: TestClient):
    """Test /api/imports and /api/imports/{run_id}/errors endpoints."""
    csv_data = "sku_id,name\nSKU-TEST,Test Name\n,Missing Name\n"
    files = {"file": ("test.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    upload_res = client.post("/api/imports/products", files=files)
    run_id = upload_res.json()["run_id"]

    # Check history
    history_res = client.get("/api/imports")
    assert history_res.status_code == 200
    runs = history_res.json()["runs"]
    assert any(r["run_id"] == run_id for r in runs)

    # Check errors endpoint
    err_res = client.get(f"/api/imports/{run_id}/errors")
    assert err_res.status_code == 200
    errs = err_res.json()
    assert len(errs) >= 1
    assert errs[0]["error_code"] == "MISSING_FIELD"


def _seed_sales_master_data(client: TestClient):
    """Seeds prerequisite product and location master records for sales testing."""
    prod_csv = (
        "sku_id,name,category,unit,case_pack,shelf_life_days\n"
        "SKU-DET-001,Sparkle Detergent Powder 1kg,Home Care,piece,12,730\n"
        "SKU-TEA-003,Assam Gold Tea 500g,Beverages,piece,24,540\n"
        "SKU-BIS-002,Golden Crunch Biscuits 200g,Packaged Food,piece,48,270\n"
    )
    client.post("/api/imports/products", files={"file": ("p.csv", io.BytesIO(prod_csv.encode("utf-8")), "text/csv")})

    loc_csv = (
        "location_id,name,location_type,region,city\n"
        "LOC-DC-PUN,Pune Distributor Godown,distributor_warehouse,West,Pune\n"
        "LOC-RET-NAS01,Nashik Retail Store 01,retail_destination,West,Nashik\n"
    )
    client.post("/api/imports/locations", files={"file": ("l.csv", io.BytesIO(loc_csv.encode("utf-8")), "text/csv")})


def test_valid_sales_csv_import_fifteen_sample_records(client: TestClient):
    """Test 1: Valid Sales History CSV import with 15 sample records."""
    _seed_sales_master_data(client)

    sales_csv_path = os.path.join(os.path.dirname(__file__), "..", "test_data", "sales.csv")
    with open(sales_csv_path, "rb") as f:
        content = f.read()

    files = {"file": ("sales.csv", io.BytesIO(content), "text/csv")}
    response = client.post("/api/imports/sales", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_rows"] == 15
    assert data["valid_rows"] == 15
    assert data["rejected_rows"] == 0
    assert len(data["errors"]) == 0

    # Verify records persisted in /api/sales
    sales_res = client.get("/api/sales")
    assert sales_res.status_code == 200
    sales_list = sales_res.json()
    assert len(sales_list) == 15


def test_valid_sales_excel_import(client: TestClient):
    """Test 2: Valid Sales History Excel import (.xlsx) with 15 records."""
    _seed_sales_master_data(client)

    sales_xlsx_path = os.path.join(os.path.dirname(__file__), "..", "test_data", "sales.xlsx")
    with open(sales_xlsx_path, "rb") as f:
        content = f.read()

    files = {"file": ("sales.xlsx", io.BytesIO(content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    response = client.post("/api/imports/sales", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_rows"] == 15
    assert data["valid_rows"] == 15
    assert data["rejected_rows"] == 0


def test_sales_supported_quantity_aliases(client: TestClient):
    """Test 3: Supported quantity-column aliases (units_sold, quantity_sold, sales_quantity)."""
    _seed_sales_master_data(client)

    # 1. quantity_sold alias
    csv_1 = (
        "sku_id,location_id,sales_date,quantity_sold\n"
        "SKU-DET-001,LOC-DC-PUN,2026-10-18,22\n"
    )
    res_1 = client.post("/api/imports/sales", files={"file": ("s1.csv", io.BytesIO(csv_1.encode("utf-8")), "text/csv")})
    assert res_1.status_code == 200
    assert res_1.json()["valid_rows"] == 1
    assert res_1.json()["rejected_rows"] == 0

    # 2. units_sold alias
    csv_2 = (
        "sku_id,location_id,sales_date,units_sold\n"
        "SKU-TEA-003,LOC-DC-PUN,2026-10-18,34\n"
    )
    res_2 = client.post("/api/imports/sales", files={"file": ("s2.csv", io.BytesIO(csv_2.encode("utf-8")), "text/csv")})
    assert res_2.status_code == 200
    assert res_2.json()["valid_rows"] == 1
    assert res_2.json()["rejected_rows"] == 0

    # 3. sales_quantity alias with destination_id
    csv_3 = (
        "sku_id,destination_id,sales_date,sales_quantity\n"
        "SKU-BIS-002,LOC-RET-NAS01,2026-10-18,48\n"
    )
    res_3 = client.post("/api/imports/sales", files={"file": ("s3.csv", io.BytesIO(csv_3.encode("utf-8")), "text/csv")})
    assert res_3.status_code == 200
    assert res_3.json()["valid_rows"] == 1
    assert res_3.json()["rejected_rows"] == 0


def test_sales_missing_quantity_column_rejects(client: TestClient):
    """Test 4: Missing quantity column triggers file-level MISSING_COLUMN error and prevents persistence."""
    _seed_sales_master_data(client)

    # CSV without quantity or any alias
    csv_missing_col = (
        "sku_id,location_id,sales_date\n"
        "SKU-DET-001,LOC-DC-PUN,2026-10-18\n"
        "SKU-DET-001,LOC-DC-PUN,2026-10-19\n"
    )
    files = {"file": ("missing_qty.csv", io.BytesIO(csv_missing_col.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/sales", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["valid_rows"] == 0
    assert data["rejected_rows"] == 2
    assert len(data["errors"]) >= 1
    err = data["errors"][0]
    assert err["error_code"] == "MISSING_COLUMN"
    assert err["field_name"] == "quantity"
    assert "Expected canonical headers" in err["error_reason"]

    # Verify zero sales records persisted
    sales_res = client.get("/api/sales")
    assert sales_res.status_code == 200
    assert len(sales_res.json()) == 0


def test_sales_blank_negative_and_nonnumeric_quantities(client: TestClient):
    """Test 5: Blank, negative, and non-numeric quantities are quarantined; zero quantity is allowed."""
    _seed_sales_master_data(client)

    csv_data = (
        "sku_id,location_id,sales_date,quantity\n"
        "SKU-DET-001,LOC-DC-PUN,2026-10-18,\n"       # Blank quantity -> MISSING_FIELD
        "SKU-DET-001,LOC-DC-PUN,2026-10-19,-15\n"    # Negative quantity -> NEGATIVE_QUANTITY
        "SKU-DET-001,LOC-DC-PUN,2026-10-20,invalid\n"# Non-numeric quantity -> INVALID_NUMERIC
        "SKU-DET-001,LOC-DC-PUN,2026-10-21,0\n"      # Zero quantity -> Valid 0.0
        "SKU-DET-001,LOC-DC-PUN,2026-10-22,35\n"     # Positive quantity -> Valid 35.0
    )
    files = {"file": ("quantities.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/sales", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert data["total_rows"] == 5
    assert data["valid_rows"] == 2
    assert data["rejected_rows"] == 3

    errors_by_code = {e["error_code"]: e for e in data["errors"]}
    assert "MISSING_FIELD" in errors_by_code
    assert errors_by_code["MISSING_FIELD"]["row_index"] == 2
    assert "NEGATIVE_QUANTITY" in errors_by_code
    assert errors_by_code["NEGATIVE_QUANTITY"]["row_index"] == 3
    assert "INVALID_NUMERIC" in errors_by_code
    assert errors_by_code["INVALID_NUMERIC"]["row_index"] == 4


def test_sales_invalid_sku_location_date_and_duplicates(client: TestClient):
    """Test 6: Invalid SKU, location, date, and duplicate compound key validations."""
    _seed_sales_master_data(client)

    csv_data = (
        "sku_id,location_id,sales_date,quantity\n"
        "SKU-NONEXISTENT,LOC-DC-PUN,2026-10-18,10\n"  # UNKNOWN_SKU
        "SKU-DET-001,LOC-NONEXISTENT,2026-10-18,10\n"  # UNKNOWN_LOCATION
        ",LOC-DC-PUN,2026-10-18,10\n"                 # Missing SKU -> MISSING_FIELD
        "SKU-DET-001,,2026-10-18,10\n"                 # Missing Location -> MISSING_FIELD
        "SKU-DET-001,LOC-DC-PUN,not-a-date,10\n"       # Invalid date -> INVALID_DATE_FORMAT
        "SKU-DET-001,LOC-DC-PUN,,10\n"                 # Missing date -> MISSING_FIELD
        "SKU-DET-001,LOC-DC-PUN,2026-10-22,10\n"       # Valid row
        "SKU-DET-001,LOC-DC-PUN,2026-10-22,15\n"       # Duplicate compound key -> DUPLICATE_KEY
    )
    files = {"file": ("invalids.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    response = client.post("/api/imports/sales", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert data["valid_rows"] == 1
    assert data["rejected_rows"] == 7

    error_codes = [e["error_code"] for e in data["errors"]]
    assert "UNKNOWN_SKU" in error_codes
    assert "UNKNOWN_LOCATION" in error_codes
    assert "MISSING_FIELD" in error_codes
    assert "INVALID_DATE_FORMAT" in error_codes
    assert "DUPLICATE_KEY" in error_codes


def test_sales_import_history_and_error_report(client: TestClient):
    """Test 7: Correct import-history and error-report generation."""
    _seed_sales_master_data(client)

    csv_data = (
        "sku_id,location_id,sales_date,quantity\n"
        "SKU-DET-001,LOC-DC-PUN,2026-10-18,-50\n"
    )
    files = {"file": ("error_run.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    res = client.post("/api/imports/sales", files=files)
    assert res.status_code == 200
    run_id = res.json()["run_id"]

    # Check history contains run
    history_res = client.get("/api/imports")
    assert history_res.status_code == 200
    runs = history_res.json()["runs"]
    matched_run = next((r for r in runs if r["run_id"] == run_id), None)
    assert matched_run is not None
    assert matched_run["dataset_type"] == "sales"
    assert matched_run["rejected_rows"] == 1

    # Check specific errors report
    err_res = client.get(f"/api/imports/{run_id}/errors")
    assert err_res.status_code == 200
    errs = err_res.json()
    assert len(errs) == 1
    assert errs[0]["error_code"] == "NEGATIVE_QUANTITY"
    assert errs[0]["field_name"] == "quantity"


def test_sales_import_followed_by_forecasting_retrieval(client: TestClient):
    """Test 8: Successful import followed by correct demand-forecasting data retrieval."""
    _seed_sales_master_data(client)

    sales_csv_path = os.path.join(os.path.dirname(__file__), "..", "test_data", "sales.csv")
    with open(sales_csv_path, "rb") as f:
        files = {"file": ("sales.csv", io.BytesIO(f.read()), "text/csv")}
    upload_res = client.post("/api/imports/sales", files=files)
    assert upload_res.status_code == 200
    assert upload_res.json()["valid_rows"] == 15

    # Demand forecasting retrieval
    planner_headers = {"Authorization": "Bearer demo-planner-token"}
    forecast_res = client.get(
        "/api/forecast?sku_id=SKU-DET-001&destination_id=LOC-DC-PUN&horizon_days=7",
        headers=planner_headers,
    )
    assert forecast_res.status_code == 200
    fdata = forecast_res.json()
    assert "forecasts" in fdata
    assert len(fdata["forecasts"]) >= 1
    item = next((i for i in fdata["forecasts"] if i["sku_id"] == "SKU-DET-001" and i["destination_id"] == "LOC-DC-PUN"), None)
    assert item is not None
    assert item["daily_forecast_rate"] == 25.6
    assert item["total_forecast_demand"] > 0
    assert len(item["forecast_method"]) > 0


def test_downloaded_sales_templates_round_trip(client: TestClient):
    """Test 9: Official downloadable sales CSV and Excel templates round-trip with 15 valid records."""
    _seed_sales_master_data(client)

    # 1. Download CSV template
    csv_resp = client.get("/api/imports/templates/sales?format=csv")
    assert csv_resp.status_code == 200
    assert "quantity" in csv_resp.text
    assert "LOC-DC-PUN" in csv_resp.text

    # Re-upload CSV template
    files_csv = {"file": ("sales_template.csv", io.BytesIO(csv_resp.text.encode("utf-8")), "text/csv")}
    upload_csv = client.post("/api/imports/sales", files=files_csv)
    assert upload_csv.status_code == 200
    assert upload_csv.json()["status"] == "completed"
    assert upload_csv.json()["valid_rows"] == 15
    assert upload_csv.json()["rejected_rows"] == 0

    # 2. Download Excel template
    xlsx_resp = client.get("/api/imports/templates/sales?format=xlsx")
    assert xlsx_resp.status_code == 200

    # Re-upload Excel template
    files_xlsx = {"file": ("sales_template.xlsx", io.BytesIO(xlsx_resp.content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    upload_xlsx = client.post("/api/imports/sales", files=files_xlsx)
    assert upload_xlsx.status_code == 200
    assert upload_xlsx.json()["status"] == "completed"
    assert upload_xlsx.json()["valid_rows"] == 15
    assert upload_xlsx.json()["rejected_rows"] == 0

