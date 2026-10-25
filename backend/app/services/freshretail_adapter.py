"""Dingdong FreshRetailNet-50K Perishables Dataset Adapter.

Handles conversion of Dingdong FreshRetailNet hourly perishable retail data into StockWise canonical schemas.
Tracks out-of-stock annotations, perishable produce shelf life, and daily sales aggregation.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone


FRESHRETAIL_DOCUMENTATION = {
    "source_name": "Dingdong FreshRetailNet-50K",
    "official_url": "https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K",
    "license": "CC BY 4.0 (Creative Commons Attribution 4.0 International)",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "attribution": "Dingdong Inc. FreshRetailNet Benchmark (2024)",
    "geography": "18 Major Metros (Tier-1 and Tier-2 Cities, 898 Fresh Food Stores)",
    "product_hierarchy": "Fresh Vegetables, Fruits, Meat, Seafood, Dairy (50,000 SKUs)",
    "coverage_period": "90-day High-Frequency Time Series (Hourly Resolution)",
    "out_of_stock_tracking": "Includes explicit stockout indicators and hourly latent demand",
    "features_supported": "Short Shelf-Life Optimization, Stockout Exposure, FEFO Allocation",
}


def get_freshretail_documentation() -> Dict[str, Any]:
    """Returns the official metadata and documentation for FreshRetailNet-50K."""
    return dict(FRESHRETAIL_DOCUMENTATION)


class FreshRetailAdapter:
    @staticmethod
    def get_status() -> Dict[str, Any]:
        return get_freshretail_documentation()

    @staticmethod
    def aggregate_hourly(hourly_records: List[Dict[str, Any]]):
        return aggregate_hourly_to_daily(hourly_records)


def aggregate_hourly_to_daily(
    hourly_records: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Aggregates hourly transaction records into daily sales points and product master records.
    Detects whether stockouts occurred during the day to tag risk exposure.
    """
    products_by_sku: Dict[str, Dict[str, Any]] = {}
    sales_by_key: Dict[Tuple[str, str, str], float] = {}
    stockouts_by_key: Dict[Tuple[str, str, str], bool] = {}

    for row in hourly_records:
        sku = str(row.get("item_id", "")).strip()
        store = str(row.get("store_id", "")).strip()
        date_str = str(row.get("dt", row.get("date", ""))).strip()
        qty = float(row.get("sales", row.get("quantity", 0.0)))
        is_oos = bool(row.get("out_of_stock", False))

        sku_id = f"SKU-FRESH-{sku}"
        dest_id = f"RET-FRESH-{store}"

        if sku_id not in products_by_sku:
            cat = str(row.get("category", "Fresh Produce")).strip()
            # Perishable goods have 3 to 14 days shelf life
            products_by_sku[sku_id] = {
                "sku_id": sku_id,
                "name": f"Fresh Retail Perishable Item {sku}",
                "category": f"Perishables - {cat}",
                "unit": "crates",
                "case_pack": 1,
                "shelf_life_days": 7,
            }

        key = (sku_id, dest_id, date_str)
        sales_by_key[key] = sales_by_key.get(key, 0.0) + max(0.0, qty)
        if is_oos:
            stockouts_by_key[key] = True

    sales_list = []
    for (s_id, d_id, dt), total_qty in sales_by_key.items():
        sales_list.append({
            "sku_id": s_id,
            "destination_id": d_id,
            "sales_date": dt,
            "quantity": round(total_qty, 2),
            "stockout_flag": stockouts_by_key.get((s_id, d_id, dt), False),
        })

    meta = {
        "dataset_name": "Dingdong FreshRetailNet-50K",
        "unique_skus": len(products_by_sku),
        "total_daily_points": len(sales_list),
        "days_with_stockouts": sum(1 for s in sales_list if s["stockout_flag"]),
        "license": FRESHRETAIL_DOCUMENTATION["license"],
    }

    return list(products_by_sku.values()), sales_list, meta
