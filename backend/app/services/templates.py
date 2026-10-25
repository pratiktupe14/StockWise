import io
import csv
from typing import Dict, List, Any
import openpyxl

SAMPLE_DATASETS: Dict[str, Dict[str, Any]] = {
    "products": {
        "headers": ["sku_id", "name", "category", "unit", "case_pack", "shelf_life_days"],
        "rows": [
            ["SKU-DET-001", "Sparkle Detergent Powder 1kg", "Fabric Care", "cases", 12, 730],
            ["SKU-SOAP-002", "PureCare Bathing Soap 125g", "Personal Care", "cases", 24, 1095],
            ["SKU-TEA-003", "Assam Gold Tea 500g", "Beverages", "cases", 20, 365],
            ["SKU-BISC-004", "Crisp Crunch Wheat Biscuits 200g", "Snacks", "cases", 30, 180],
            ["SKU-SHAM-005", "SilkGlow Shampoo 340ml", "Hair Care", "cases", 16, 730],
        ],
    },
    "organizations": {
        "headers": ["org_id", "name", "org_type", "contact_email", "contact_phone", "is_active"],
        "rows": [
            ["ORG-FMCG-HUL", "Hindustan Consumer Goods Ltd", "fmcg_company", "supplychain@hcg-corp.in", "+91-22-2830-1000", True],
            ["ORG-CNF-APEX", "Apex Carrying & Forwarding Agency", "cnf_agency", "operations@apex-cnf.in", "+91-11-4560-2200", True],
            ["ORG-3PL-GATI", "Gati-KWE Logistics Fleet", "logistics_provider", "dispatch@gati-logistics.in", "+91-20-6710-5500", True],
            ["ORG-DIST-DELHI", "Delhi Capital Distributors Ltd", "distributor", "orders@delhidist.in", "+91-11-2390-8800", True],
            ["ORG-RET-SPENCER", "Spencer Retail Destinations Ltd", "retailer", "procure@spencers.in", "+91-33-2280-9900", True],
        ],
    },
    "locations": {
        "headers": ["location_id", "name", "location_type", "region", "city", "address", "owner_org_id", "operator_org_id", "storage_capacity_units", "dispatch_capacity_daily"],
        "rows": [
            ["PLANT-HARIDWAR", "Haridwar Integrated FMCG Plant", "manufacturing_plant", "North", "Haridwar", "Sector 3, SIDCUL Industrial Estate", "ORG-FMCG-HUL", "ORG-FMCG-HUL", 50000, 5000],
            ["WH-CENTRAL-01", "Central Plant Warehouse North", "central_warehouse", "North", "Gurgaon", "Plot 14, Industrial Area, Gurgaon", "ORG-FMCG-HUL", "ORG-FMCG-HUL", 30000, 3000],
            ["CNF-FACILITY-PUN", "Pune C&F Agent Stock Point", "cnf_facility", "West", "Pune", "Chakan MIDC Phase 2", "ORG-FMCG-HUL", "ORG-CNF-APEX", 15000, 1500],
            ["WH-REGIONAL-02", "West Regional Distribution Centre", "regional_warehouse", "West", "Mumbai", "Bhiwandi Logistics Hub, Mumbai", "ORG-FMCG-HUL", "ORG-FMCG-HUL", 25000, 2500],
            ["DIST-NORTH-01", "Delhi Capital Distributors Hub", "distributor_warehouse", "North", "New Delhi", "Ring Road Hub, New Delhi", "ORG-DIST-DELHI", "ORG-DIST-DELHI", 8000, 800],
            ["RET-DELHI-001", "SuperMart Flagship Connaught Place", "retail_destination", "North", "New Delhi", "Inner Circle, New Delhi", "ORG-RET-SPENCER", "ORG-RET-SPENCER", 2000, 200],
        ],
    },
    "inventory": {
        "headers": ["snapshot_id", "sku_id", "location_id", "owner_org_id", "on_hand", "reserved", "blocked", "confirmed_incoming", "batch_number", "as_of_date"],
        "rows": [
            ["SNAP-20261024", "SKU-DET-001", "WH-CENTRAL-01", "ORG-FMCG-HUL", 1200, 200, 50, 0, "BAT-DET-01", "2026-10-24"],
            ["SNAP-20261024", "SKU-SOAP-002", "WH-CENTRAL-01", "ORG-FMCG-HUL", 850, 100, 0, 150, "BAT-SOAP-01", "2026-10-24"],
            ["SNAP-20261024", "SKU-TEA-003", "CNF-FACILITY-PUN", "ORG-FMCG-HUL", 400, 50, 20, 0, "BAT-TEA-02", "2026-10-24"],
            ["SNAP-20261024", "SKU-BISC-004", "DIST-NORTH-01", "ORG-DIST-DELHI", 120, 30, 0, 0, "BAT-BISC-01", "2026-10-24"],
            ["SNAP-20261024", "SKU-SHAM-005", "WH-REGIONAL-02", "ORG-FMCG-HUL", 600, 80, 0, 100, "BAT-SHAM-01", "2026-10-24"],
        ],
    },
    "sales": {
        "headers": ["sku_id", "destination_id", "sales_date", "quantity"],
        "rows": [
            ["SKU-DET-001", "DIST-NORTH-01", "2026-10-20", 45],
            ["SKU-DET-001", "DIST-NORTH-01", "2026-10-21", 52],
            ["SKU-SOAP-002", "CNF-FACILITY-PUN", "2026-10-20", 30],
            ["SKU-TEA-003", "RET-DELHI-001", "2026-10-21", 25],
            ["SKU-BISC-004", "RET-DELHI-001", "2026-10-22", 40],
        ],
    },
    "routes": {
        "headers": ["from_location_id", "to_location_id", "carrier_agency_id", "lead_time_days", "cost_rate", "capacity_units", "sku_eligibility", "pricing_basis"],
        "rows": [
            ["PLANT-HARIDWAR", "WH-CENTRAL-01", "ORG-3PL-GATI", 1.0, 30.0, 3000, "all", "per_unit"],
            ["WH-CENTRAL-01", "DIST-NORTH-01", "ORG-3PL-GATI", 1.5, 45.0, 500, "all", "per_unit"],
            ["WH-CENTRAL-01", "WH-REGIONAL-02", "ORG-3PL-GATI", 3.0, 85.0, 1500, "all", "per_unit"],
            ["WH-REGIONAL-02", "CNF-FACILITY-PUN", "ORG-3PL-GATI", 1.0, 25.0, 1000, "all", "per_unit"],
            ["DIST-NORTH-01", "RET-DELHI-001", "ORG-3PL-GATI", 0.5, 18.0, 200, "all", "per_unit"],
            ["WH-CENTRAL-01", "CNF-FACILITY-PUN", "ORG-3PL-GATI", 3.5, 95.0, 800, "all", "per_unit"],
        ],
    },
}


def generate_template_csv(dataset_type: str) -> str:
    template = SAMPLE_DATASETS.get(dataset_type)
    if not template:
        raise ValueError(f"Unknown dataset type: {dataset_type}")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(template["headers"])
    for row in template["rows"]:
        writer.writerow(row)
    return output.getvalue()


def generate_template_excel(dataset_type: str) -> bytes:
    template = SAMPLE_DATASETS.get(dataset_type)
    if not template:
        raise ValueError(f"Unknown dataset type: {dataset_type}")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Template_{dataset_type.capitalize()}"

    ws.append(template["headers"])
    for row in template["rows"]:
        ws.append(row)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
