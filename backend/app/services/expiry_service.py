from datetime import date
from typing import List, Optional, Dict, Any


def calculate_batch_expiry_risk(
    batch: Any,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Calculates deterministic expiry risk metrics for a single batch/inventory record.
    Preserves dispatchable stock rule: max(0.0, on_hand - reserved - blocked).
    Missing expiry dates remain unknown, never fabricated.
    """
    as_of_date = as_of or (getattr(batch, "as_of_date", None) or date.today())
    expiry_date = getattr(batch, "expiry_date", None)
    on_hand = float(getattr(batch, "on_hand", 0.0) or 0.0)
    reserved = float(getattr(batch, "reserved", 0.0) or 0.0)
    blocked = float(getattr(batch, "blocked", 0.0) or 0.0)

    # Core dispatchable calculation
    dispatchable = max(0.0, float(on_hand - reserved - blocked))

    if expiry_date is None:
        days_remaining = None
        risk_category = "unknown"
        is_expired = False
    else:
        days_remaining = (expiry_date - as_of_date).days
        if days_remaining <= 0:
            risk_category = "expired"
            is_expired = True
        elif days_remaining <= 15:
            risk_category = "critical"
            is_expired = False
        elif days_remaining <= 30:
            risk_category = "high"
            is_expired = False
        elif days_remaining <= 60:
            risk_category = "medium"
            is_expired = False
        else:
            risk_category = "healthy"
            is_expired = False

    # Expired or zero-dispatchable stock is strictly ineligible for dispatch
    is_dispatchable = (not is_expired) and (dispatchable > 0.0)

    product_name = None
    if hasattr(batch, "product") and batch.product:
        product_name = batch.product.name

    location_name = None
    if hasattr(batch, "location") and batch.location:
        location_name = batch.location.name

    return {
        "id": getattr(batch, "id", None),
        "snapshot_id": getattr(batch, "snapshot_id", ""),
        "sku_id": getattr(batch, "sku_id", ""),
        "product_name": product_name,
        "location_id": getattr(batch, "location_id", ""),
        "location_name": location_name,
        "batch_number": getattr(batch, "batch_number", None),
        "expiry_date": expiry_date,
        "days_remaining": days_remaining,
        "risk_category": risk_category,
        "on_hand": on_hand,
        "reserved": reserved,
        "blocked": blocked,
        "dispatchable_quantity": dispatchable,
        "is_dispatchable": is_dispatchable,
        "owner_org_id": getattr(batch, "owner_org_id", None),
    }


def summarize_expiry_risk(
    batches: List[Any],
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Aggregates expiry risk statistics across a collection of inventory records.
    """
    total_batches = len(batches)
    expired_batches = 0
    expired_units = 0.0
    critical_batches = 0
    critical_units = 0.0
    high_risk_batches = 0
    high_risk_units = 0.0
    medium_risk_batches = 0
    medium_risk_units = 0.0
    healthy_batches = 0
    healthy_units = 0.0
    unknown_expiry_batches = 0
    unknown_expiry_units = 0.0
    total_dispatchable_units = 0.0

    items = []
    for b in batches:
        item = calculate_batch_expiry_risk(b, as_of=as_of)
        items.append(item)

        disp = item["dispatchable_quantity"]
        cat = item["risk_category"]

        if cat == "expired":
            expired_batches += 1
            # Expired units reflect remaining physical on_hand
            expired_units += item["on_hand"]
        elif cat == "critical":
            critical_batches += 1
            critical_units += disp
            total_dispatchable_units += disp
        elif cat == "high":
            high_risk_batches += 1
            high_risk_units += disp
            total_dispatchable_units += disp
        elif cat == "medium":
            medium_risk_batches += 1
            medium_risk_units += disp
            total_dispatchable_units += disp
        elif cat == "healthy":
            healthy_batches += 1
            healthy_units += disp
            total_dispatchable_units += disp
        elif cat == "unknown":
            unknown_expiry_batches += 1
            unknown_expiry_units += disp
            total_dispatchable_units += disp

    return {
        "total_batches": total_batches,
        "expired_batches": expired_batches,
        "expired_units": round(expired_units, 2),
        "critical_batches": critical_batches,
        "critical_units": round(critical_units, 2),
        "high_risk_batches": high_risk_batches,
        "high_risk_units": round(high_risk_units, 2),
        "medium_risk_batches": medium_risk_batches,
        "medium_risk_units": round(medium_risk_units, 2),
        "healthy_batches": healthy_batches,
        "healthy_units": round(healthy_units, 2),
        "unknown_expiry_batches": unknown_expiry_batches,
        "unknown_expiry_units": round(unknown_expiry_units, 2),
        "total_dispatchable_units": round(total_dispatchable_units, 2),
        "items": items,
    }


def allocate_fefo_batches(
    batches: List[Any],
    demand_quantity: float,
    min_remaining_shelf_life_days: int = 0,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Reusable First-Expired, First-Out (FEFO) allocation engine.
    Prioritizes eligible batches strictly by earliest valid expiry date.
    - Excludes expired batches (days_remaining <= 0).
    - Excludes batches below minimum remaining shelf life if specified.
    - Excludes fully blocked/reserved batches.
    - Deterministic tie-breaking by expiry_date ASC, then dispatchable DESC, then batch_number ASC.
    - Explicitly computes unmet demand when available stock is insufficient.
    """
    if demand_quantity <= 0:
        return {
            "demand_quantity": 0.0,
            "total_allocated": 0.0,
            "unmet_demand": 0.0,
            "is_fully_allocated": True,
            "min_remaining_shelf_life_days": min_remaining_shelf_life_days,
            "allocations": [],
        }

    as_of_date = as_of or date.today()

    # Step 1: Filter to eligible dispatchable batches
    eligible = []
    for b in batches:
        info = calculate_batch_expiry_risk(b, as_of=as_of_date)
        # Exclude expired
        if info["risk_category"] == "expired":
            continue
        # Exclude below min shelf life if required
        if min_remaining_shelf_life_days > 0 and info["days_remaining"] is not None:
            if info["days_remaining"] < min_remaining_shelf_life_days:
                continue
        # Exclude zero or negative dispatchable stock
        if info["dispatchable_quantity"] <= 0.0:
            continue
        eligible.append(info)

    # Step 2: Deterministic FEFO sorting
    # Known earliest expiry comes first. Batches with unknown expiry come after known batches.
    # Tie-break: highest available quantity, then alphabetical batch_number, then id
    def fefo_sort_key(item: Dict[str, Any]):
        has_known_expiry = 0 if item["expiry_date"] is not None else 1
        exp_date = item["expiry_date"] or date.max
        # Negative dispatchable to prioritize larger batch if tie
        qty_tie = -item["dispatchable_quantity"]
        batch_tie = item["batch_number"] or ""
        id_tie = item["id"] or 0
        return (has_known_expiry, exp_date, qty_tie, batch_tie, id_tie)

    eligible.sort(key=fefo_sort_key)

    # Step 3: Greedily allocate up to demand_quantity
    remaining_demand = float(demand_quantity)
    allocations = []
    total_allocated = 0.0

    for item in eligible:
        if remaining_demand <= 0.0:
            break

        available = item["dispatchable_quantity"]
        allocated = min(available, remaining_demand)

        allocations.append({
            "snapshot_id": item["snapshot_id"],
            "batch_number": item["batch_number"],
            "location_id": item["location_id"],
            "expiry_date": item["expiry_date"],
            "days_remaining": item["days_remaining"],
            "allocated_quantity": round(allocated, 2),
            "available_before_allocation": round(available, 2),
            "remaining_after_allocation": round(available - allocated, 2),
        })

        total_allocated += allocated
        remaining_demand -= allocated

    unmet_demand = max(0.0, round(float(demand_quantity - total_allocated), 2))
    is_fully_allocated = unmet_demand <= 1e-6

    return {
        "demand_quantity": round(float(demand_quantity), 2),
        "total_allocated": round(float(total_allocated), 2),
        "unmet_demand": unmet_demand,
        "is_fully_allocated": is_fully_allocated,
        "min_remaining_shelf_life_days": min_remaining_shelf_life_days,
        "allocations": allocations,
    }
