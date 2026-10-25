from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.entities import InventorySnapshot, Location, Product, Route
from app.schemas.planning import RiskAnalysisItem, RiskAnalysisResponse
from app.services.forecast_service import compute_demand_forecast


def analyze_inventory_risks(
    db: Session,
    horizon_days: int = 7,
    snapshot_id: Optional[str] = None,
    destination_id: Optional[str] = None,
    sku_id: Optional[str] = None,
) -> RiskAnalysisResponse:
    """
    Evaluates inventory risk position across all destination nodes:
    - Enforces Phase 2 inventory accounting: Dispatchable = max(0, OH - Res - Blk).
    - Excludes in-transit stock double counting.
    - Considers confirmed incoming receipts only if arrival qualifies for planning cutoff.
    - Calculates stock cover days, demand gaps, and safety buffer replenishment.
    - Checks earliest feasible replenishment lead times from active permitted corridors.
    - Identifies unavoidable stockout risks where cover days < earliest lead time.
    """
    # 1. Obtain demand forecasts for the given horizon
    forecast_resp = compute_demand_forecast(db, horizon_days=horizon_days, sku_id=sku_id, destination_id=destination_id)
    forecast_map = {(f.sku_id, f.destination_id): f for f in forecast_resp.forecasts}

    # 2. Pre-fetch network metadata: locations, products, and permitted active routes
    products = {p.sku_id: p.name for p in db.query(Product).all()}
    locations = {l.location_id: l for l in db.query(Location).all()}

    # Active permitted inbound routes for each destination: destination_id -> list of Route
    active_routes = db.query(Route).filter(Route.is_active == True).all()
    inbound_routes_by_dest: Dict[str, List[Route]] = {}
    for r in active_routes:
        if r.to_location_id not in inbound_routes_by_dest:
            inbound_routes_by_dest[r.to_location_id] = []
        inbound_routes_by_dest[r.to_location_id].append(r)

    # 3. Fetch inventory positions
    inv_query = db.query(InventorySnapshot)
    if snapshot_id:
        inv_query = inv_query.filter(InventorySnapshot.snapshot_id == snapshot_id.strip())
    else:
        # Default to company operational inventory, isolating benchmark datasets
        inv_query = inv_query.filter(
            InventorySnapshot.owner_org_id != "BENCHMARK-COMPANY",
            InventorySnapshot.snapshot_id != "SNAP-BENCHMARK-PUBLIC",
        )
    if destination_id:
        inv_query = inv_query.filter(InventorySnapshot.location_id == destination_id.strip())
    if sku_id:
        inv_query = inv_query.filter(InventorySnapshot.sku_id == sku_id.strip())

    inv_records = inv_query.all()
    if not inv_records and not snapshot_id:
        fallback_query = db.query(InventorySnapshot)
        if destination_id:
            fallback_query = fallback_query.filter(InventorySnapshot.location_id == destination_id.strip())
        if sku_id:
            fallback_query = fallback_query.filter(InventorySnapshot.sku_id == sku_id.strip())
        inv_records = fallback_query.all()

    # Group inventory by (sku_id, location_id)
    inv_by_node: Dict[Tuple[str, str], InventorySnapshot] = {
        (rec.sku_id, rec.location_id): rec for rec in inv_records
    }

    # Destination nodes that service retail / end customer demand
    dest_types = {"retail_destination", "distributor_warehouse", "regional_warehouse", "company_warehouse", "cnf_facility"}
    forecast_destinations = {f.destination_id for f in forecast_resp.forecasts}
    target_dest_ids = [
        loc_id for loc_id, loc in locations.items()
        if (loc.location_type in dest_types or loc_id in forecast_destinations) and loc.is_active
    ]
    if destination_id:
        target_dest_ids = [d for d in target_dest_ids if d == destination_id.strip()]

    target_sku_ids = list(products.keys())
    if sku_id:
        target_sku_ids = [s for s in target_sku_ids if s == sku_id.strip()]

    risk_items: List[RiskAnalysisItem] = []
    critical_cnt = 0
    high_cnt = 0
    medium_cnt = 0
    low_cnt = 0

    now = datetime.now(timezone.utc)
    cutoff_date = now + timedelta(days=horizon_days)

    for d_id in sorted(target_dest_ids):
        dest_loc = locations.get(d_id)
        dest_name = dest_loc.name if dest_loc else d_id

        # Determine earliest feasible replenishment lead time from active permitted inbound routes
        inbound = inbound_routes_by_dest.get(d_id, [])
        valid_lead_times = [
            float(r.lead_time_days) for r in inbound if r.lead_time_days is not None and r.lead_time_days > 0
        ]
        earliest_lt = min(valid_lead_times) if valid_lead_times else None

        for s_id in sorted(target_sku_ids):
            prod_name = products.get(s_id, s_id)
            fc = forecast_map.get((s_id, d_id))

            daily_demand = fc.daily_forecast_rate if fc else 0.0
            total_forecast = fc.total_forecast_demand if fc else 0.0

            # Inventory position at this destination node
            inv = inv_by_node.get((s_id, d_id))
            # Use unified inventory calculation engine
            from app.services.inventory_service import (
                compute_dispatchable_stock,
                compute_projected_available_stock,
                compute_stock_cover_days,
                compute_safety_stock,
                compute_target_stock,
                compute_replenishment_gap,
                compute_excess_stock,
                evaluate_batch_shelf_life,
            )

            on_hand = float(inv.on_hand) if inv else 0.0
            reserved = float(inv.reserved) if inv else 0.0
            blocked = float(inv.blocked) if inv else 0.0
            confirmed_inc = float(inv.confirmed_incoming) if inv else 0.0

            dispatchable = compute_dispatchable_stock(on_hand, reserved, blocked)
            eligible_stock, _ = compute_projected_available_stock(
                on_hand=on_hand,
                reserved=reserved,
                blocked=blocked,
                confirmed_incoming=confirmed_inc,
                planning_cutoff=cutoff_date,
            )

            # Stock Cover Days
            cover_days = compute_stock_cover_days(eligible_stock, daily_demand)

            # Projected Demand Gap
            demand_gap = max(0.0, round(total_forecast - eligible_stock, 1))

            # Target safety stock & total target stock
            safety_target = compute_safety_stock(daily_demand, buffer_days=3.0)
            target_stock = compute_target_stock(daily_demand, horizon_days=horizon_days, buffer_days=3.0)

            # Replenishment gap and excess stock
            replenishment_need = compute_replenishment_gap(target_stock, eligible_stock)
            excess_stock = compute_excess_stock(eligible_stock, target_stock)

            # Batch shelf-life evaluation
            batch_expiry_info = evaluate_batch_shelf_life(
                expiry_date=inv.expiry_date if inv else None,
                reference_date=now.date(),
                horizon_days=horizon_days,
            )
            batch_risk_flag = batch_expiry_info.get("risk_flag") if batch_expiry_info.get("has_expiry_data") else None

            # Expected stockout window and unfulfillable demand
            stockout_window = None
            unfulfillable_demand = 0.0
            if daily_demand > 0 and cover_days < horizon_days:
                stockout_day = cover_days
                stockout_window = f"Day {stockout_day:.1f} to Day {horizon_days}"
                if earliest_lt is not None and earliest_lt > cover_days:
                    unfulfillable_days = min(float(horizon_days), earliest_lt) - cover_days
                    unfulfillable_demand = round(unfulfillable_days * daily_demand, 1)

            # Determine Risk Level and Primary Risk Factor
            if fc and fc.data_sufficiency == "insufficient_history":
                risk_level = "medium"
                primary_factor = "Sparse sales history: demand uncertainty requires baseline monitoring."
                medium_cnt += 1
            elif daily_demand == 0.0:
                risk_level = "low"
                primary_factor = "Zero forecast demand across horizon."
                low_cnt += 1
            elif earliest_lt is not None and cover_days < earliest_lt:
                risk_level = "critical"
                primary_factor = (
                    f"CRITICAL: Stockout in {cover_days:.1f} days precedes earliest feasible "
                    f"replenishment arrival ({earliest_lt:.1f} days). Unavoidable stockout window!"
                )
                critical_cnt += 1
            elif earliest_lt is not None and cover_days <= (earliest_lt + 2.0):
                risk_level = "high"
                primary_factor = (
                    f"HIGH: Cover ({cover_days:.1f}d) is at replenishment threshold ({earliest_lt:.1f}d + 2d buffer)."
                )
                high_cnt += 1
            elif earliest_lt is not None and cover_days <= (earliest_lt * 2.0):
                risk_level = "medium"
                primary_factor = f"MEDIUM: Cover ({cover_days:.1f}d) within normal reorder cycle."
                medium_cnt += 1
            elif cover_days <= horizon_days:
                risk_level = "high"
                primary_factor = f"Stock covers {cover_days:.1f} days within {horizon_days}-day horizon."
                high_cnt += 1
            else:
                risk_level = "low"
                primary_factor = f"Adequate stock cover ({cover_days:.1f} days) exceeds planning horizon."
                low_cnt += 1

            risk_items.append(
                RiskAnalysisItem(
                    sku_id=s_id,
                    product_name=prod_name,
                    destination_id=d_id,
                    destination_name=dest_name,
                    horizon_days=horizon_days,
                    daily_forecast_rate=daily_demand,
                    total_forecast_demand=total_forecast,
                    on_hand=on_hand,
                    reserved=reserved,
                    blocked=blocked,
                    confirmed_incoming=confirmed_inc,
                    dispatchable_stock=dispatchable,
                    cover_days=cover_days,
                    demand_gap=demand_gap,
                    safety_stock_target=safety_target,
                    target_stock=target_stock,
                    replenishment_need=replenishment_need,
                    excess_stock=excess_stock,
                    earliest_replenishment_lead_time_days=earliest_lt,
                    expected_stockout_window=stockout_window,
                    unfulfillable_demand=unfulfillable_demand,
                    batch_expiry_risk=batch_risk_flag,
                    risk_level=risk_level,
                    primary_risk_factor=primary_factor,
                )
            )

    return RiskAnalysisResponse(
        horizon_days=horizon_days,
        critical_count=critical_cnt,
        high_count=high_cnt,
        medium_count=medium_cnt,
        low_count=low_cnt,
        items=risk_items,
    )
