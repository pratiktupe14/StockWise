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
            ["SKU-BIS-002", "Golden Crunch Biscuits 200g", "Packaged Food", "cases", 48, 270],
            ["SKU-BISC-004", "Crisp Crunch Wheat Biscuits 200g", "Snacks", "cases", 30, 180],
            ["SKU-OIL-004", "SunPure Cooking Oil 1L", "Edible Oil", "cases", 15, 365],
            ["SKU-SOAP-005", "FreshCare Bath Soap 100g", "Personal Care", "cases", 72, 900],
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
        "headers": ["location_id", "name", "location_type", "region", "city", "address", "owner_org_id", "operator_org_id", "storage_capacity_units", "dispatch_capacity_daily", "is_active"],
        "rows": [
            ["LOC-PLT-NAS", "Nashik Manufacturing Plant", "manufacturing_plant", "West", "Nashik", "Ambad MIDC Industrial Area, Nashik", "", "", 50000, 12000, True],
            ["LOC-WH-MUM", "Mumbai Central Warehouse", "company_warehouse", "West", "Mumbai", "Plot 12 MIDC Industrial Area, Bhiwandi, Mumbai", "", "", 30000, 8000, True],
            ["LOC-RDC-PUN", "Pune Regional Distribution Centre", "regional_warehouse", "West", "Pune", "Chakan MIDC Logistics Corridor, Pune", "", "", 18000, 5000, True],
            ["LOC-DC-PUN", "Pune Distributor Godown", "distributor_warehouse", "West", "Pune", "Wagholi Logistics Park, Pune", "", "", 6000, 1800, True],
            ["LOC-DC-KOL", "Kolhapur Distributor Godown", "distributor_warehouse", "West", "Kolhapur", "Shiroli MIDC Industrial Area, Kolhapur", "", "", 4500, 1200, True],
            ["LOC-RET-NAS01", "Nashik Retail Store 01", "retail_destination", "West", "Nashik", "College Road Market, Nashik", "", "", 1200, 250, True],
            ["LOC-RET-PUN01", "Pune Retail Store 01", "retail_destination", "West", "Pune", "FC Road Commercial Hub, Pune", "", "", 1000, 200, True],
        ],
    },
    "inventory": {
        "headers": ["snapshot_id", "sku_id", "location_id", "owner_org_id", "on_hand", "reserved", "blocked", "confirmed_incoming", "batch_number", "as_of_date"],
        "rows": [
            ["SNAP-20261024", "SKU-DET-001", "LOC-WH-MUM", "", 1200, 200, 50, 0, "BAT-DET-01", "2026-10-24"],
            ["SNAP-20261024", "SKU-SOAP-002", "LOC-WH-MUM", "", 850, 100, 0, 150, "BAT-SOAP-01", "2026-10-24"],
            ["SNAP-20261024", "SKU-TEA-003", "LOC-RDC-PUN", "", 400, 50, 20, 0, "BAT-TEA-02", "2026-10-24"],
            ["SNAP-20261024", "SKU-BISC-004", "LOC-DC-PUN", "", 120, 30, 0, 0, "BAT-BISC-01", "2026-10-24"],
            ["SNAP-20261024", "SKU-SHAM-005", "LOC-DC-KOL", "", 600, 80, 0, 100, "BAT-SHAM-01", "2026-10-24"],
        ],
    },
    "sales": {
        "headers": ["sku_id", "location_id", "sales_date", "quantity"],
        "rows": [
            ["SKU-DET-001", "LOC-DC-PUN", "2026-10-18", 22],
            ["SKU-DET-001", "LOC-DC-PUN", "2026-10-19", 25],
            ["SKU-DET-001", "LOC-DC-PUN", "2026-10-20", 21],
            ["SKU-DET-001", "LOC-DC-PUN", "2026-10-21", 29],
            ["SKU-DET-001", "LOC-DC-PUN", "2026-10-22", 31],
            ["SKU-TEA-003", "LOC-DC-PUN", "2026-10-18", 34],
            ["SKU-TEA-003", "LOC-DC-PUN", "2026-10-19", 37],
            ["SKU-TEA-003", "LOC-DC-PUN", "2026-10-20", 40],
            ["SKU-TEA-003", "LOC-DC-PUN", "2026-10-21", 36],
            ["SKU-TEA-003", "LOC-DC-PUN", "2026-10-22", 44],
            ["SKU-BIS-002", "LOC-RET-NAS01", "2026-10-18", 48],
            ["SKU-BIS-002", "LOC-RET-NAS01", "2026-10-19", 51],
            ["SKU-BIS-002", "LOC-RET-NAS01", "2026-10-20", 46],
            ["SKU-BIS-002", "LOC-RET-NAS01", "2026-10-21", 59],
            ["SKU-BIS-002", "LOC-RET-NAS01", "2026-10-22", 63],
        ],
    },
    "routes": {
        "headers": ["from_location_id", "to_location_id", "carrier_agency_id", "lead_time_days", "cost_rate", "capacity_units", "sku_eligibility", "pricing_basis"],
        "rows": [
            ["LOC-PLT-NAS", "LOC-WH-MUM", "", 1.0, 30.0, 3000, "all", "per_unit"],
            ["LOC-WH-MUM", "LOC-RDC-PUN", "", 1.5, 45.0, 1500, "all", "per_unit"],
            ["LOC-RDC-PUN", "LOC-DC-PUN", "", 1.0, 25.0, 800, "all", "per_unit"],
            ["LOC-RDC-PUN", "LOC-DC-KOL", "", 2.0, 35.0, 600, "all", "per_unit"],
            ["LOC-DC-PUN", "LOC-RET-PUN01", "", 0.5, 15.0, 200, "all", "per_unit"],
            ["LOC-DC-KOL", "LOC-RET-NAS01", "", 1.5, 20.0, 200, "all", "per_unit"],
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
