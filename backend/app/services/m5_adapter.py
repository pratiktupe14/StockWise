"""Walmart M5 Forecasting Dataset Adapter.

Handles conversion of Kaggle M5 competition sales time series into StockWise canonical schemas.
Documents authentication requirements and competition terms boundaries.
Supports wide-to-long transformation from daily columns (d_1, d_2, ...) with calendar date mapping.
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd


M5_DOCUMENTATION = {
    "source_name": "Walmart M5 Forecasting Accuracy",
    "official_url": "https://www.kaggle.com/competitions/m5-forecasting-accuracy/data",
    "license": "Kaggle Competition Rules (Academic & Non-commercial Benchmarking)",
    "access_status": "Blocked without user Kaggle authentication token",
    "blocker_details": (
        "Kaggle competitions require individual user authentication, manual acceptance of competition terms, "
        "and a personal API key (~/.kaggle/kaggle.json). Automated downloads without credentials are intentionally "
        "quarantined by Kaggle servers (HTTP 401/404)."
    ),
    "geography": "United States (California: CA_1-4, Texas: TX_1-3, Wisconsin: WI_1-3)",
    "product_hierarchy": "HOBBIES, HOUSEHOLD, FOODS (3,049 items across 10 stores)",
    "coverage_period": "2011-01-29 to 2016-06-19 (1,941 days)",
    "remediation_instructions": [
        "1. Log in to Kaggle and navigate to https://www.kaggle.com/competitions/m5-forecasting-accuracy/rules",
        "2. Click 'I Understand and Accept' to bind your account to competition terms",
        "3. Download sales_train_evaluation.csv and calendar.csv to data/downloads/m5/",
        "4. Run the StockWise M5 Ingestion Adapter via Dataset Management console",
    ],
}


def get_m5_access_status() -> Dict[str, Any]:
    """Returns the documented access and blocker status for Walmart M5."""
    return dict(M5_DOCUMENTATION)


class M5Adapter:
    @staticmethod
    def get_status() -> Dict[str, Any]:
        return get_m5_access_status()

    @staticmethod
    def parse_and_transform(sales_csv_path: str, calendar_csv_path: Optional[str] = None, item_limit: int = 50, days_limit: int = 90):
        return parse_and_transform_m5_data(sales_csv_path, calendar_csv_path, item_limit, days_limit)


def parse_and_transform_m5_data(
    sales_csv_path: str,
    calendar_csv_path: Optional[str] = None,
    item_limit: int = 50,
    days_limit: int = 90,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Transforms raw Kaggle M5 sales wide-format data into canonical StockWise records:
    - Products Master (sku_id, name, category, unit, case_pack, shelf_life_days)
    - Sales History (sku_id, destination_id, sales_date, quantity)
    """
    if not os.path.exists(sales_csv_path):
        raise FileNotFoundError(
            f"M5 source file not found at {sales_csv_path}. {M5_DOCUMENTATION['blocker_details']}"
        )

    # Read sales slice
    df_sales = pd.read_csv(sales_csv_path, nrows=item_limit)

    # Build calendar map d_x -> YYYY-MM-DD
    day_to_date: Dict[str, str] = {}
    if calendar_csv_path and os.path.exists(calendar_csv_path):
        cal_df = pd.read_csv(calendar_csv_path)
        for _, row in cal_df.iterrows():
            day_to_date[str(row["d"])] = str(row["date"])
    else:
        # Fallback date generator starting from baseline 2016-01-01
        base_dt = datetime(2016, 1, 1)
        for i in range(1, 2000):
            d_key = f"d_{i}"
            cur_dt = base_dt + pd.Timedelta(days=i - 1)
            day_to_date[d_key] = cur_dt.strftime("%Y-%m-%d")

    # Day columns present in sales file
    day_cols = [c for c in df_sales.columns if c.startswith("d_")][:days_limit]

    products_list = []
    sales_list = []

    for _, row in df_sales.iterrows():
        raw_item = str(row["item_id"]).strip()
        sku_id = f"SKU-M5-{raw_item}"
        dept_id = str(row.get("dept_id", "FOODS")).strip()
        cat_id = str(row.get("cat_id", "General")).strip()
        store_id = str(row.get("store_id", "STORE-US-01")).strip()
        dest_id = f"RET-US-{store_id}"

        # Category and shelf life inference
        shelf_life = 90 if "FOOD" in cat_id.upper() else 365
        products_list.append({
            "sku_id": sku_id,
            "name": f"Walmart M5 {raw_item} ({dept_id})",
            "category": f"US Retail {cat_id}",
            "unit": "cases",
            "case_pack": 12,
            "shelf_life_days": shelf_life,
        })

        # Melt days into sales rows
        for d_col in day_cols:
            qty = float(row[d_col])
            sales_date = day_to_date.get(d_col, "2016-01-01")
            sales_list.append({
                "sku_id": sku_id,
                "destination_id": dest_id,
                "sales_date": sales_date,
                "quantity": qty,
            })

    meta = {
        "dataset_name": "Walmart M5 Forecasting Accuracy",
        "items_parsed": len(products_list),
        "days_transformed": len(day_cols),
        "total_sales_observations": len(sales_list),
        "geography_label": "United States Benchmark Network",
        "attribution": "Makridakis, S., et al. (2022). The M5 Competition.",
    }

    return products_list, sales_list, meta
