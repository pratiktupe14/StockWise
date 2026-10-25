import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.entities import (
    InventorySnapshot,
    Location,
    Product,
    Route,
    SalesHistory,
    Shipment,
    StockMovement,
    ShipmentEvent,
    Organization,
)
from app.schemas.redistribution import (
    RedistributionRecommendation,
    RedistributionRejectedCandidate,
    RedistributionSummaryResponse,
    CreateRedistributionProposalRequest,
)
from app.schemas.network import ShipmentProposalRequest, ShipmentResponse
from app.services.expiry_service import calculate_batch_expiry_risk
from app.services.network_service import propose_shipment
from app.core.security import AuthenticatedUser


def generate_redistribution_recommendations(
    db: Session,
    current_user: AuthenticatedUser,
    sku_id: Optional[str] = None,
    source_location_id: Optional[str] = None,
    max_expiry_days: int = 60,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Identifies surplus or near-expiry finished goods at a source facility and
    recommends transferring them to an eligible destination with unmet demand
    and sufficient remaining shelf life.

    Strict rules:
    - Same-owner restriction: Source inventory must belong to user's authorized organization.
    - Rejects expired (days_remaining <= 0) and blocked stock.
    - Rejects transfers where stock would arrive expired or fail minimum shelf-life.
    - Caps transfer quantity by source dispatchable stock and destination unmet demand.
    - Transparent deterministic ranking based on expiry urgency and service impact.
    - Never modifies physical inventory or auto-dispatches shipments.
    """
    today = as_of or date.today()

    # Step 1: Query source inventory candidates scoped strictly to authorized organization
    query = (
        db.query(InventorySnapshot)
        .join(Product, InventorySnapshot.sku_id == Product.sku_id)
        .join(Location, InventorySnapshot.location_id == Location.location_id)
    )

    if current_user.role != "admin":
        if current_user.org_id:
            query = query.filter(InventorySnapshot.owner_org_id == current_user.org_id)
        else:
            return {
                "generated_at": datetime.now(timezone.utc),
                "total_candidates_analyzed": 0,
                "recommendations_count": 0,
                "potential_units_saved": 0.0,
                "total_estimated_transport_cost": 0.0,
                "recommendations": [],
                "rejected_candidates": [],
            }

    if sku_id:
        query = query.filter(InventorySnapshot.sku_id == sku_id.strip())
    if source_location_id:
        query = query.filter(InventorySnapshot.location_id == source_location_id.strip())

    source_snapshots = query.all()

    recommendations: List[RedistributionRecommendation] = []
    rejected_candidates: List[RedistributionRejectedCandidate] = []
    total_analyzed = 0

    for src_inv in source_snapshots:
        total_analyzed += 1
        sku = src_inv.sku_id
        src_loc = src_inv.location_id
        src_owner = src_inv.owner_org_id or current_user.org_id or ""

        # Calculate dispatchable stock and expiry risk
        risk_info = calculate_batch_expiry_risk(src_inv, as_of=today)
        dispatchable_qty = risk_info["dispatchable_quantity"]
        days_remaining = risk_info["days_remaining"]
        batch_no = src_inv.batch_number

        # Reject if zero dispatchable units
        if dispatchable_qty <= 0:
            rejected_candidates.append(
                RedistributionRejectedCandidate(
                    sku_id=sku,
                    source_location_id=src_loc,
                    destination_location_id="ALL",
                    batch_number=batch_no,
                    rejection_reason=f"No dispatchable stock available (on_hand={src_inv.on_hand}, reserved={src_inv.reserved}, blocked={src_inv.blocked})",
                )
            )
            continue

        # Reject expired stock
        if risk_info["risk_category"] == "expired":
            rejected_candidates.append(
                RedistributionRejectedCandidate(
                    sku_id=sku,
                    source_location_id=src_loc,
                    destination_location_id="ALL",
                    batch_number=batch_no,
                    rejection_reason=f"Stock has already expired ({days_remaining}d remaining). Expired stock cannot be redistributed.",
                )
            )
            continue

        # Check candidate surplus or expiry eligibility
        # If expiry date exists and days_remaining <= max_expiry_days, it qualifies
        # If no expiry date, only qualify if dispatchable stock exceeds 50 units (surplus)
        is_near_expiry = (days_remaining is not None and days_remaining <= max_expiry_days)
        is_surplus = (dispatchable_qty > 50.0)

        if not (is_near_expiry or is_surplus):
            continue

        # Step 2: Find permitted outbound transport corridors from this source facility
        routes = (
            db.query(Route)
            .filter(
                Route.from_location_id == src_loc,
                Route.to_location_id != src_loc,
                Route.is_active == True,
            )
            .all()
        )

        if not routes:
            rejected_candidates.append(
                RedistributionRejectedCandidate(
                    sku_id=sku,
                    source_location_id=src_loc,
                    destination_location_id="ALL",
                    batch_number=batch_no,
                    rejection_reason=f"No active permitted outbound transport routes found from '{src_loc}'",
                )
            )
            continue

        for route in routes:
            dest_loc = route.to_location_id

            # Verify route lead time validity
            lead_time = float(route.lead_time_days or 0.0)
            if lead_time <= 0:
                rejected_candidates.append(
                    RedistributionRejectedCandidate(
                        sku_id=sku,
                        source_location_id=src_loc,
                        destination_location_id=dest_loc,
                        batch_number=batch_no,
                        rejection_reason=f"Route #{route.id} has invalid lead time ({lead_time} days)",
                    )
                )
                continue

            # Calculate shelf life at destination arrival
            arrival_date = today + timedelta(days=int(lead_time))
            if days_remaining is not None:
                shelf_life_at_arrival = days_remaining - int(lead_time)
                if shelf_life_at_arrival <= 0:
                    rejected_candidates.append(
                        RedistributionRejectedCandidate(
                            sku_id=sku,
                            source_location_id=src_loc,
                            destination_location_id=dest_loc,
                            batch_number=batch_no,
                            rejection_reason=(
                                f"Stock would expire before arrival: lead time {lead_time}d exceeds or matches "
                                f"remaining shelf life {days_remaining}d (shelf life at arrival: {shelf_life_at_arrival}d)"
                            ),
                        )
                    )
                    continue

                # FMCG standard: require at least 10 days remaining shelf life at destination dock
                if shelf_life_at_arrival < 10:
                    rejected_candidates.append(
                        RedistributionRejectedCandidate(
                            sku_id=sku,
                            source_location_id=src_loc,
                            destination_location_id=dest_loc,
                            batch_number=batch_no,
                            rejection_reason=(
                                f"Insufficient shelf life upon arrival ({shelf_life_at_arrival}d). "
                                f"Minimum 10 days required for retail redistribution."
                            ),
                        )
                    )
                    continue
            else:
                shelf_life_at_arrival = 999  # Unknown/indefinite

            # Step 3: Compute destination unmet demand / inventory shortfall
            dest_inv_records = (
                db.query(InventorySnapshot)
                .filter(
                    InventorySnapshot.sku_id == sku,
                    InventorySnapshot.location_id == dest_loc,
                )
                .all()
            )
            dest_dispatchable = sum(inv.dispatchable_stock for inv in dest_inv_records)

            # Check sales history at destination to determine consumption rate
            avg_daily_sales = (
                db.query(func.avg(SalesHistory.quantity))
                .filter(
                    SalesHistory.sku_id == sku,
                    SalesHistory.destination_id == dest_loc,
                )
                .scalar()
            )

            if avg_daily_sales and float(avg_daily_sales) > 0:
                target_demand = float(avg_daily_sales) * 14.0  # 14-day planning horizon demand
            else:
                # Default target buffer if destination stock is depleted
                target_demand = 80.0 if dest_dispatchable == 0 else 0.0

            destination_shortfall = max(0.0, float(target_demand - dest_dispatchable))

            if destination_shortfall <= 0:
                rejected_candidates.append(
                    RedistributionRejectedCandidate(
                        sku_id=sku,
                        source_location_id=src_loc,
                        destination_location_id=dest_loc,
                        batch_number=batch_no,
                        rejection_reason=f"Destination '{dest_loc}' already has sufficient stock ({dest_dispatchable:.1f} dispatchable units; shortfall is 0)",
                    )
                )
                continue

            # Step 4: Cap recommended quantity
            recommended_qty = min(float(dispatchable_qty), float(destination_shortfall))
            if recommended_qty <= 0:
                continue

            # Transport cost calculation
            cost_rate = float(route.cost_rate or 0.0)
            est_cost = round(recommended_qty * cost_rate, 2)

            # Step 5: Deterministic Priority Scoring (0 - 100)
            urgency_score = 0.0
            if days_remaining is not None:
                if days_remaining <= 15:
                    urgency_score = 50.0
                elif days_remaining <= 30:
                    urgency_score = 35.0
                elif days_remaining <= 60:
                    urgency_score = 20.0
                else:
                    urgency_score = 5.0
            else:
                urgency_score = 10.0

            service_score = min(35.0, (recommended_qty / max(1.0, destination_shortfall)) * 35.0)
            lead_time_score = max(0.0, 15.0 - lead_time)
            total_priority = round(urgency_score + service_score + lead_time_score, 1)

            # Explainable Rationale
            days_str = f"{days_remaining}d" if days_remaining is not None else "Unknown"
            rationale = (
                f"Redistribute {recommended_qty:.0f} units from '{src_loc}' to '{dest_loc}'. "
                f"Urgency: {risk_info['risk_category'].upper()} ({days_str} remaining). "
                f"Destination shortfall: {destination_shortfall:.0f} units. "
                f"Transit lead time: {lead_time:.0f}d (ETA: {arrival_date.isoformat()}; "
                f"arrival shelf life: {shelf_life_at_arrival}d). "
                f"Estimated transport cost: ₹{est_cost:,.2f}."
            )

            rec_id = f"REC-REDIST-{uuid.uuid4().hex[:8].upper()}"
            src_name = src_inv.location.name if src_inv.location else src_loc
            dest_loc_obj = db.query(Location).filter(Location.location_id == dest_loc).first()
            dest_name = dest_loc_obj.name if dest_loc_obj else dest_loc
            prod_name = src_inv.product.name if src_inv.product else sku

            recommendations.append(
                RedistributionRecommendation(
                    recommendation_id=rec_id,
                    sku_id=sku,
                    product_name=prod_name,
                    source_location_id=src_loc,
                    source_location_name=src_name,
                    destination_location_id=dest_loc,
                    destination_location_name=dest_name,
                    batch_number=batch_no,
                    expiry_date=src_inv.expiry_date,
                    days_remaining=days_remaining,
                    risk_category=risk_info["risk_category"],
                    source_available_units=dispatchable_qty,
                    destination_unmet_demand=round(destination_shortfall, 1),
                    recommended_quantity=round(recommended_qty, 1),
                    lead_time_days=lead_time,
                    expected_delivery_date=arrival_date,
                    shelf_life_days_at_arrival=shelf_life_at_arrival,
                    estimated_transport_cost=est_cost,
                    priority_score=total_priority,
                    rationale=rationale,
                    owner_org_id=src_owner,
                )
            )

    # Sort recommendations deterministically by priority score DESC, then days remaining ASC
    recommendations.sort(
        key=lambda r: (-r.priority_score, r.days_remaining if r.days_remaining is not None else 9999, -r.recommended_quantity)
    )

    total_units_saved = sum(r.recommended_quantity for r in recommendations)
    total_transport_cost = sum(r.estimated_transport_cost for r in recommendations)

    return {
        "generated_at": datetime.now(timezone.utc),
        "total_candidates_analyzed": total_analyzed,
        "recommendations_count": len(recommendations),
        "potential_units_saved": round(total_units_saved, 1),
        "total_estimated_transport_cost": round(total_transport_cost, 2),
        "recommendations": recommendations,
        "rejected_candidates": rejected_candidates,
    }


def create_redistribution_shipment_proposal(
    db: Session,
    current_user: AuthenticatedUser,
    payload: CreateRedistributionProposalRequest,
) -> Shipment:
    """
    Transforms an authorized redistribution recommendation into a formal Shipment proposal.
    Reuses existing proposal lifecycle and enforces:
    - User's organization ownership boundary.
    - Source dispatchable stock availability check.
    - Proposed shipment status: 'proposed', approval_status: 'pending'.
    - Does NOT alter physical stock or auto-dispatch.
    """
    # 1. Enforce ownership and tenant isolation
    inv = (
        db.query(InventorySnapshot)
        .filter(
            InventorySnapshot.sku_id == payload.sku_id,
            InventorySnapshot.location_id == payload.source_location_id,
        )
        .first()
    )

    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source inventory for SKU '{payload.sku_id}' at facility '{payload.source_location_id}' not found.",
        )

    if current_user.role != "admin":
        if inv.owner_org_id and inv.owner_org_id != current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source inventory for SKU '{payload.sku_id}' not found.",
            )

    # 2. Build shipment proposal request
    batch_str = f" [Batch: {payload.batch_number}]" if payload.batch_number else ""
    proposal_notes = f"AUTHS_REDISTRIBUTION: {payload.notes or 'Expiry prevention transfer'}{batch_str}"

    req = ShipmentProposalRequest(
        sku_id=payload.sku_id,
        quantity=payload.quantity,
        source_location_id=payload.source_location_id,
        destination_location_id=payload.destination_location_id,
        owner_org_id=inv.owner_org_id or current_user.org_id,
        planning_run_id=f"REDIST-{uuid.uuid4().hex[:6].upper()}",
        notes=proposal_notes,
    )

    # 3. Reuse existing propose_shipment service
    return propose_shipment(db, req)
