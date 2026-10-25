"""
StockWise Inventory Calculation Engine (PRD Section 4 & Phase 4.5 Feature 3).

Unified, tested service for FMCG multi-echelon inventory accounting.
Defines formal mathematical models for:
- Dispatchable Stock
- Eligible Projected Available Stock
- Stock Cover Days
- Safety Stock Target
- Target Stock
- Replenishment Gap
- Excess Stock
- Batch Shelf-Life & Expiry Exposure
- Ownership Protection for Independent Distributor Nodes
"""

from datetime import datetime, date, timezone, timedelta
from typing import Optional, Dict, Any, Tuple


def compute_dispatchable_stock(
    on_hand: float,
    reserved: float = 0.0,
    blocked: float = 0.0,
) -> float:
    """
    Computes current physically dispatchable stock at a source node.
    Formula: max(0, On-Hand - Reserved - Blocked)
    CRITICAL RULE: Incoming and in-transit units must NEVER be counted as currently dispatchable.
    """
    oh = max(0.0, float(on_hand or 0.0))
    res = max(0.0, float(reserved or 0.0))
    blk = max(0.0, float(blocked or 0.0))
    return max(0.0, round(oh - res - blk, 2))


def compute_projected_available_stock(
    on_hand: float,
    reserved: float = 0.0,
    blocked: float = 0.0,
    confirmed_incoming: float = 0.0,
    arrival_date: Optional[datetime] = None,
    planning_cutoff: Optional[datetime] = None,
) -> Tuple[float, bool]:
    """
    Computes projected available stock at a destination node for a planning horizon.
    Eligible stock = Dispatchable + Confirmed Incoming (if arrival <= planning cutoff).
    Incoming stock is counted exactly once and only when arrival date qualifies.

    Returns:
        (projected_available_stock, incoming_was_eligible)
    """
    dispatchable = compute_dispatchable_stock(on_hand, reserved, blocked)
    inc = max(0.0, float(confirmed_incoming or 0.0))

    if inc <= 0.0:
        return (dispatchable, False)

    # Check arrival eligibility against cutoff
    is_eligible = True
    if arrival_date and planning_cutoff:
        # Standardize both to aware datetimes if needed
        arr = arrival_date if arrival_date.tzinfo else arrival_date.replace(tzinfo=timezone.utc)
        cut = planning_cutoff if planning_cutoff.tzinfo else planning_cutoff.replace(tzinfo=timezone.utc)
        if arr > cut:
            is_eligible = False

    if is_eligible:
        return (round(dispatchable + inc, 2), True)
    return (dispatchable, False)


def compute_stock_cover_days(
    available_stock: float,
    daily_consumption_rate: float,
) -> float:
    """
    Calculates stock cover days.
    If daily consumption rate is 0, returns 999.0 (indefinite cover).
    """
    stock = max(0.0, float(available_stock or 0.0))
    daily = float(daily_consumption_rate or 0.0)
    if daily <= 0.0:
        return 999.0
    return round(stock / daily, 1)


def compute_safety_stock(
    daily_demand: float,
    buffer_days: float = 3.0,
) -> float:
    """
    Computes safety buffer requirement in units.
    Default standard: 3.0 days of daily consumption rate.
    """
    daily = max(0.0, float(daily_demand or 0.0))
    days = max(0.0, float(buffer_days or 0.0))
    return round(daily * days, 1)


def compute_target_stock(
    daily_demand: float,
    horizon_days: int = 7,
    buffer_days: float = 3.0,
) -> float:
    """
    Computes total target stock position required at a destination:
    Target Stock = (Daily Demand * Horizon Days) + Safety Stock Buffer
    """
    daily = max(0.0, float(daily_demand or 0.0))
    cycle_demand = daily * max(1, horizon_days)
    safety = compute_safety_stock(daily, buffer_days=buffer_days)
    return round(cycle_demand + safety, 1)


def compute_replenishment_gap(
    target_stock: float,
    eligible_projected_stock: float,
) -> float:
    """
    Computes the net replenishment requirement.
    Formula: max(0, Target Stock - Eligible Projected Available Stock)
    """
    target = max(0.0, float(target_stock or 0.0))
    eligible = max(0.0, float(eligible_projected_stock or 0.0))
    return max(0.0, round(target - eligible, 1))


def compute_excess_stock(
    eligible_projected_stock: float,
    target_stock: float,
) -> float:
    """
    Computes excess inventory position above the target level.
    Formula: max(0, Eligible Projected Available Stock - Target Stock)
    NOTE: Excess inventory must NOT be automatically dispatched without human review.
    """
    eligible = max(0.0, float(eligible_projected_stock or 0.0))
    target = max(0.0, float(target_stock or 0.0))
    return max(0.0, round(eligible - target, 1))


def evaluate_batch_shelf_life(
    expiry_date: Optional[date],
    reference_date: Optional[date] = None,
    horizon_days: int = 7,
) -> Dict[str, Any]:
    """
    Evaluates whether a batch has impending shelf-life or expiry exposure.
    """
    if not expiry_date:
        return {
            "has_expiry_data": False,
            "days_to_expiry": None,
            "is_expired": False,
            "expires_within_horizon": False,
            "risk_flag": "no_batch_data",
        }

    ref = reference_date or datetime.now(timezone.utc).date()
    if isinstance(ref, datetime):
        ref = ref.date()
    if isinstance(expiry_date, datetime):
        expiry_date = expiry_date.date()

    days_left = (expiry_date - ref).days

    if days_left <= 0:
        return {
            "has_expiry_data": True,
            "days_to_expiry": days_left,
            "is_expired": True,
            "expires_within_horizon": True,
            "risk_flag": "expired_blocked",
        }
    elif days_left <= horizon_days:
        return {
            "has_expiry_data": True,
            "days_to_expiry": days_left,
            "is_expired": False,
            "expires_within_horizon": True,
            "risk_flag": "critical_expiry_window",
        }
    elif days_left <= (horizon_days * 3):
        return {
            "has_expiry_data": True,
            "days_to_expiry": days_left,
            "is_expired": False,
            "expires_within_horizon": False,
            "risk_flag": "nearing_expiry_monitor",
        }
    else:
        return {
            "has_expiry_data": True,
            "days_to_expiry": days_left,
            "is_expired": False,
            "expires_within_horizon": False,
            "risk_flag": "healthy_shelf_life",
        }


def is_distributor_owned_stock(
    owner_org_type: Optional[str],
) -> bool:
    """
    Evaluates ownership restriction.
    Independently owned distributor stock must be protected from company allocation.
    """
    if not owner_org_type:
        return False
    return owner_org_type.lower().strip() in {
        "independent_distributor",
        "distributor",
        "retailer",
    }
