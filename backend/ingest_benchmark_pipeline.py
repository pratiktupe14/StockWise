"""Ingest Benchmark Pipeline CLI.

Reproducibly executes the end-to-end dataset ingestion pipeline:
1. OpenStreetMap Verified Indian FMCG Logistics Network & OSRM Routes
2. UCI Online Retail II Real Products, Curated Sales History & FEFO Balances
3. Lineage verification and audit run generation

Usage:
    python ingest_benchmark_pipeline.py [--force]
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.database import SessionLocal
from app.services.dataset_service import (
    ingest_osm_india_network,
    ingest_uci_online_retail_benchmark,
    get_dataset_registry_and_readiness,
)


def main():
    parser = argparse.ArgumentParser(description="Ingest StockWise Benchmark Datasets")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing records")
    args = parser.parse_args()

    print("=== StockWise Reproducible Dataset Ingestion Pipeline ===")
    db = SessionLocal()
    try:
        # Step 1: Ingest OSM India Logistics Network
        print("\n[Step 1/2] Ingesting OpenStreetMap Indian Logistics Network...")
        osm_res = ingest_osm_india_network(db, force_reload=args.force)
        print(f"  -> Locations Ingested: {osm_res['locations_ingested']}")
        print(f"  -> Routes Ingested: {osm_res['routes_ingested']}")

        # Step 2: Ingest UCI Online Retail II Benchmark
        print("\n[Step 2/2] Ingesting UCI Online Retail II Benchmark Data...")
        uci_res = ingest_uci_online_retail_benchmark(db, force_reload=args.force)
        print(f"  -> Products Ingested: {uci_res['products_ingested']}")
        print(f"  -> Sales Observations Ingested: {uci_res['sales_records_ingested']}")
        print(f"  -> Inventory Balances Ingested: {uci_res['inventory_snapshots_ingested']}")

        # Step 3: Print Readiness Summary
        print("\n=== Ingestion Complete & Lineage Verified ===")
        readiness = get_dataset_registry_and_readiness(db)
        print("Database Counts:", readiness["database_counts"])
        print("Operational Readiness:", readiness["operational_readiness"])

    except Exception as exc:
        print(f"ERROR during pipeline ingestion: {exc}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
