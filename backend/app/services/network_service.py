import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.entities import (
    Organization,
    Location,
    Product,
    InventorySnapshot,
    Route,
    Shipment,
    StockMovement,
    ShipmentEvent,
)
from app.schemas.network import (
    ShipmentProposalRequest,
    ShipmentApprovalRequest,
    ShipmentStatusUpdateRequest,
    RouteEligibilityCheck,
    UnserviceableLocationInfo,
    NetworkEligibilityResponse,
)
from app.services.idempotency_service import with_row_lock


def utcnow():
    return datetime.now(timezone.utc)


def check_route_eligibility(
    route: Route,
    sku: Optional[Product] = None,
    qty: Optional[float] = None,
) -> Tuple[bool, List[str]]:
    """
    Evaluates whether a transport route is eligible and feasible for distribution.
    Enforces business rules from PRD Section 5 & Acceptance Criteria.
    """
    reasons = []

    # 1. Route active status
    if not route.is_active:
        reasons.append("Route is currently deactivated / inactive.")

    # 2. Source facility active status
    if route.from_location and not route.from_location.is_active:
        reasons.append(f"Source facility '{route.from_location.name}' is inactive.")

    # 3. Destination facility active status
    if route.to_location and not route.to_location.is_active:
        reasons.append(f"Destination facility '{route.to_location.name}' is inactive.")

    # 4. Lead time validity
    if route.lead_time_days is None or route.lead_time_days <= 0:
        reasons.append("Invalid or missing lead time: must be > 0 days.")

    # 5. Cost rate validity
    if route.cost_rate is None or route.cost_rate < 0:
        reasons.append("Invalid or missing cost rate: must be >= 0.")

    # 6. Self-referencing check
    if route.from_location_id == route.to_location_id:
        reasons.append("Self-referencing route: source and destination cannot be identical.")

    # 7. SKU Eligibility
    if sku and route.sku_eligibility and route.sku_eligibility.lower() != "all":
        allowed = [s.strip().lower() for s in route.sku_eligibility.split(",")]
        sku_cat = (sku.category or "").lower()
        sku_id = sku.sku_id.lower()
        if sku_id not in allowed and sku_cat not in allowed:
            reasons.append(f"SKU '{sku.sku_id}' is not in permitted list: {route.sku_eligibility}")

    # 8. Quantity constraints
    if qty is not None:
        if route.min_shipment_qty is not None and qty < route.min_shipment_qty:
            reasons.append(f"Shipment quantity ({qty}) below minimum threshold ({route.min_shipment_qty}).")
        if route.max_shipment_qty is not None and qty > route.max_shipment_qty:
            reasons.append(f"Shipment quantity ({qty}) exceeds maximum capacity ({route.max_shipment_qty}).")

    is_eligible = len(reasons) == 0
    return is_eligible, reasons


def analyze_network_eligibility(db: Session) -> NetworkEligibilityResponse:
    """
    Analyzes entire network, evaluates all corridors, and finds unserviceable destinations.
    """
    all_locations = db.query(Location).all()
    all_routes = db.query(Route).all()

    active_locations = [loc for loc in all_locations if loc.is_active]
    active_routes = [r for r in all_routes if r.is_active]

    route_checks: List[RouteEligibilityCheck] = []
    serviceable_dest_ids = set()

    for r in all_routes:
        eligible, reasons = check_route_eligibility(r)
        if eligible:
            serviceable_dest_ids.add(r.to_location_id)

        route_checks.append(
            RouteEligibilityCheck(
                route_id=r.id,
                from_location_id=r.from_location_id,
                from_location_name=r.from_location.name if r.from_location else r.from_location_id,
                to_location_id=r.to_location_id,
                to_location_name=r.to_location.name if r.to_location else r.to_location_id,
                carrier_agency_name=r.carrier_agency.name if r.carrier_agency else None,
                is_eligible=eligible,
                rejection_reasons=reasons,
                lead_time_days=r.lead_time_days,
                cost_rate=r.cost_rate,
            )
        )

    # Destination locations that should receive shipments
    destination_types = {"retail_destination", "distributor_warehouse", "regional_warehouse", "cnf_facility"}
    unserviceable: List[UnserviceableLocationInfo] = []

    for loc in all_locations:
        if loc.location_type in destination_types:
            if not loc.is_active:
                unserviceable.append(
                    UnserviceableLocationInfo(
                        location_id=loc.location_id,
                        name=loc.name,
                        location_type=loc.location_type,
                        region=loc.region,
                        reason="Facility is deactivated / inactive in master network.",
                    )
                )
            elif loc.location_id not in serviceable_dest_ids:
                unserviceable.append(
                    UnserviceableLocationInfo(
                        location_id=loc.location_id,
                        name=loc.name,
                        location_type=loc.location_type,
                        region=loc.region,
                        reason="No active, feasible transport lane configured to this destination.",
                    )
                )

    summary = (
        f"Analyzed {len(all_locations)} locations ({len(active_locations)} active) and "
        f"{len(all_routes)} corridors ({len([rc for rc in route_checks if rc.is_eligible])} eligible). "
        f"{len(unserviceable)} destination(s) require corridor configuration."
    )

    return NetworkEligibilityResponse(
        total_locations=len(all_locations),
        active_locations=len(active_locations),
        total_routes=len(all_routes),
        active_routes=len(active_routes),
        eligible_corridors=route_checks,
        unserviceable_destinations=unserviceable,
        summary_message=summary,
    )


def propose_shipment(db: Session, proposal: ShipmentProposalRequest) -> Shipment:
    """
    Proposes a shipment with strict validation:
    - Route must exist, be active, and permit SKU (cannot use forbidden routes).
    - Source stock must be sufficient (cannot exceed current dispatchable stock).
    - Prevents double-counting and creates audit stock movement.
    """
    # 1. Verify Product
    product = db.query(Product).filter(Product.sku_id == proposal.sku_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product with SKU '{proposal.sku_id}' not found.",
        )

    # 2. Verify Source & Destination Locations
    source = db.query(Location).filter(Location.location_id == proposal.source_location_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source location '{proposal.source_location_id}' not found.",
        )
    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source location '{source.name}' is inactive.",
        )

    dest = db.query(Location).filter(Location.location_id == proposal.destination_location_id).first()
    if not dest:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Destination location '{proposal.destination_location_id}' not found.",
        )
    if not dest.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Destination location '{dest.name}' is inactive.",
        )

    # 3. Verify Route and Eligibility (Rule: Shipment cannot use forbidden route)
    route = (
        db.query(Route)
        .filter(
            Route.from_location_id == proposal.source_location_id,
            Route.to_location_id == proposal.destination_location_id,
        )
        .first()
    )
    if not route:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"FORBIDDEN_ROUTE: No permitted transport lane exists from "
                f"'{source.name}' ({source.location_id}) to '{dest.name}' ({dest.location_id})."
            ),
        )

    is_eligible, reasons = check_route_eligibility(route, sku=product, qty=proposal.quantity)
    if not is_eligible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"INELIGIBLE_ROUTE: Route cannot be used. Reasons: {'; '.join(reasons)}",
        )

    # 4. Check Source Dispatchable Stock (Rule: Cannot exceed configured source stock)
    # Dispatchable stock = max(0, on_hand - reserved - blocked)
    inv_records = (
        db.query(InventorySnapshot)
        .filter(
            InventorySnapshot.sku_id == proposal.sku_id,
            InventorySnapshot.location_id == proposal.source_location_id,
        )
        .all()
    )

    total_dispatchable = sum(rec.dispatchable_stock for rec in inv_records)

    # Subtract already proposed active shipments for this SKU & source
    pending_shipments = (
        db.query(func.coalesce(func.sum(Shipment.quantity), 0.0))
        .filter(
            Shipment.sku_id == proposal.sku_id,
            Shipment.source_location_id == proposal.source_location_id,
            Shipment.status.in_(["proposed", "approved", "ready_for_dispatch", "in_transit"]),
        )
        .scalar()
    )

    available_for_shipment = max(0.0, total_dispatchable - float(pending_shipments))

    if proposal.quantity > available_for_shipment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"INSUFFICIENT_DISPATCHABLE_STOCK: Requested {proposal.quantity} units, "
                f"but source facility '{source.name}' only has {available_for_shipment:.1f} "
                f"uncommitted dispatchable units (Total dispatchable: {total_dispatchable:.1f}, "
                f"Pending commitments: {pending_shipments:.1f})."
            ),
        )

    # 5. Determine Owner & Carrier
    owner_org_id = proposal.owner_org_id
    if not owner_org_id:
        # Default to first inventory record's owner or source facility owner
        if inv_records and inv_records[0].owner_org_id:
            owner_org_id = inv_records[0].owner_org_id
        elif source.owner_org_id:
            owner_org_id = source.owner_org_id

    carrier_agency_id = proposal.carrier_agency_id or route.carrier_agency_id

    # 6. Calculate cost and ETA
    cost = float(proposal.quantity * route.cost_rate)
    dispatch_time = proposal.estimated_dispatch_date or utcnow()
    arrival_time = dispatch_time + timedelta(days=float(route.lead_time_days))

    shipment_id = f"SHP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

    shipment = Shipment(
        shipment_id=shipment_id,
        sku_id=proposal.sku_id,
        quantity=proposal.quantity,
        source_location_id=proposal.source_location_id,
        destination_location_id=proposal.destination_location_id,
        owner_org_id=owner_org_id,
        carrier_agency_id=carrier_agency_id,
        route_id=route.id,
        estimated_dispatch_date=dispatch_time,
        estimated_arrival_date=arrival_time,
        estimated_transport_cost=cost,
        status="proposed",
        planning_run_id=proposal.planning_run_id,
        approval_status="pending",
        approval_notes=proposal.notes,
    )
    db.add(shipment)

    # Record traceable movement
    movement = StockMovement(
        movement_id=f"MOV-{uuid.uuid4().hex[:8].upper()}",
        shipment_id=shipment_id,
        sku_id=proposal.sku_id,
        source_location_id=proposal.source_location_id,
        destination_location_id=proposal.destination_location_id,
        quantity=proposal.quantity,
        movement_type="proposed_dispatch",
        status="proposed",
        timestamp=utcnow(),
        notes=f"Proposed allocation of {proposal.quantity} units via Route #{route.id}",
    )
    db.add(movement)

    # Initial auditable event
    init_event = ShipmentEvent(
        event_id=f"EVT-{utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
        shipment_id=shipment_id,
        from_status="none",
        to_status="proposed",
        actor_id="distribution_intelligence",
        actor_role="planner",
        notes=proposal.notes or f"Proposed {proposal.quantity} units from {proposal.source_location_id} to {proposal.destination_location_id}",
        created_at=utcnow(),
    )
    db.add(init_event)

    db.commit()
    db.refresh(shipment)
    return shipment


def approve_shipment(
    db: Session,
    shipment_id: str,
    approval_req: ShipmentApprovalRequest,
) -> Shipment:
    """
    Records governance approval decision.
    CRITICAL PRD BOUNDARY: Approval authorizes the recommendation; it NEVER automatically
    dispatches vehicles, claims goods are delivered, or silently consumes physical stock.
    """
    shipment = with_row_lock(db.query(Shipment).filter(Shipment.shipment_id == shipment_id), db).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found.",
        )

    if shipment.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Shipment '{shipment_id}' has already been decided ({shipment.approval_status}).",
        )

    now = utcnow()
    if approval_req.approved:
        # Revalidate live source inventory and route constraints before approval with exclusive row lock
        src_inv = with_row_lock(
            db.query(InventorySnapshot).filter(
                InventorySnapshot.sku_id == shipment.sku_id,
                InventorySnapshot.location_id == shipment.source_location_id,
            ),
            db,
        ).first()
        live_dispatchable = src_inv.dispatchable_stock if src_inv else 0.0
        if live_dispatchable < float(shipment.quantity):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Stale recommendation: live dispatchable stock ({live_dispatchable:.1f}) at source "
                    f"'{shipment.source_location_id}' is insufficient for required quantity ({shipment.quantity:.1f}). "
                    f"Replanning is required before approval."
                ),
            )

        if shipment.route_id:
            route = db.query(Route).filter(Route.id == shipment.route_id).first()
            if not route or not route.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Stale recommendation: route '{shipment.route_id}' is inactive or deleted. "
                        f"Replanning is required before approval."
                    ),
                )

        shipment.approval_status = "approved"
        shipment.status = "approved"
        shipment.approved_by = approval_req.authorized_user_id
        shipment.approval_notes = approval_req.notes or "Authorized by planner/approver."
        shipment.updated_at = now

        # Add movement record
        movement = StockMovement(
            movement_id=f"MOV-{uuid.uuid4().hex[:8].upper()}",
            shipment_id=shipment.shipment_id,
            sku_id=shipment.sku_id,
            source_location_id=shipment.source_location_id,
            destination_location_id=shipment.destination_location_id,
            quantity=shipment.quantity,
            movement_type="approved_allocation",
            status="approved",
            timestamp=now,
            notes=f"Approved by {approval_req.authorized_user_id}. Operational boundary: No direct vehicle dispatch.",
        )
        db.add(movement)

        # Record audit event
        appr_event = ShipmentEvent(
            event_id=f"EVT-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
            shipment_id=shipment.shipment_id,
            from_status="proposed",
            to_status="approved",
            actor_id=approval_req.authorized_user_id,
            actor_role="supply_chain_planner",
            notes=shipment.approval_notes,
            created_at=now,
        )
        db.add(appr_event)
    else:
        shipment.approval_status = "rejected"
        shipment.status = "rejected"
        shipment.approved_by = approval_req.authorized_user_id
        shipment.approval_notes = approval_req.notes or "Rejected by planner/approver."
        shipment.updated_at = now

        movement = StockMovement(
            movement_id=f"MOV-{uuid.uuid4().hex[:8].upper()}",
            shipment_id=shipment.shipment_id,
            sku_id=shipment.sku_id,
            source_location_id=shipment.source_location_id,
            destination_location_id=shipment.destination_location_id,
            quantity=shipment.quantity,
            movement_type="rejected_proposal",
            status="rejected",
            timestamp=now,
            notes=f"Proposal rejected by {approval_req.authorized_user_id}.",
        )
        db.add(movement)

        rej_event = ShipmentEvent(
            event_id=f"EVT-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
            shipment_id=shipment.shipment_id,
            from_status="proposed",
            to_status="rejected",
            actor_id=approval_req.authorized_user_id,
            actor_role="supply_chain_planner",
            notes=shipment.approval_notes,
            created_at=now,
        )
        db.add(rej_event)

    db.commit()
    db.refresh(shipment)
    return shipment


def update_shipment_status(
    db: Session,
    shipment_id: str,
    status_req: ShipmentStatusUpdateRequest,
) -> Shipment:
    """
    Updates operational shipment status with strict lifecycle transition guards,
    inventory reservation/consumption, and full event audit logging.
    """
    shipment = with_row_lock(db.query(Shipment).filter(Shipment.shipment_id == shipment_id), db).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found.",
        )

    allowed_transitions = {
        "proposed": {"approved", "rejected", "cancelled"},
        "approved": {"ready_for_dispatch", "cancelled"},
        "ready_for_dispatch": {"in_transit", "cancelled"},
        "in_transit": {"delivered"},
        "delivered": set(),
        "rejected": set(),
        "cancelled": set(),
    }

    if status_req.status not in allowed_transitions.get(shipment.status, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"INVALID_STATE_TRANSITION: Cannot transition shipment '{shipment_id}' "
                f"from '{shipment.status}' to '{status_req.status}'. "
                f"Allowed transitions: {sorted(list(allowed_transitions.get(shipment.status, set())))}"
            ),
        )

    # Inventory and state management per transition
    now = utcnow()
    prev_status = shipment.status

    if status_req.status == "ready_for_dispatch":
        # Reserve stock on source inventory with exclusive row lock
        inv_records = with_row_lock(
            db.query(InventorySnapshot).filter(
                InventorySnapshot.sku_id == shipment.sku_id,
                InventorySnapshot.location_id == shipment.source_location_id,
            ),
            db,
        ).all()
        total_disp = sum(r.dispatchable_stock for r in inv_records)
        if total_disp < shipment.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"INSUFFICIENT_STOCK: Source warehouse has {total_disp} units, required {shipment.quantity}.",
            )
        rem = shipment.quantity
        for inv in inv_records:
            avail = max(0.0, float(inv.on_hand - inv.reserved - inv.blocked))
            if avail > 0:
                res = min(rem, avail)
                inv.reserved += res
                rem -= res
                if rem <= 0:
                    break

    elif status_req.status == "in_transit":
        # Consume stock from source with exclusive row lock
        inv_records = with_row_lock(
            db.query(InventorySnapshot).filter(
                InventorySnapshot.sku_id == shipment.sku_id,
                InventorySnapshot.location_id == shipment.source_location_id,
            ),
            db,
        ).all()
        rem = shipment.quantity
        for inv in inv_records:
            if inv.on_hand > 0:
                deduct = min(rem, float(inv.on_hand))
                inv.on_hand = max(0.0, float(inv.on_hand - deduct))
                inv.reserved = max(0.0, float(inv.reserved - deduct))
                rem -= deduct
                if rem <= 0:
                    break
        shipment.actual_pickup_date = now

    elif status_req.status == "delivered":
        # Credit destination inventory with exclusive row lock
        dest_inv = with_row_lock(
            db.query(InventorySnapshot).filter(
                InventorySnapshot.sku_id == shipment.sku_id,
                InventorySnapshot.location_id == shipment.destination_location_id,
            ),
            db,
        ).first()
        if dest_inv:
            dest_inv.on_hand += shipment.quantity
        else:
            dest_inv = InventorySnapshot(
                snapshot_id=f"SNAP-DELIV-{now.strftime('%Y%m%d')}",
                sku_id=shipment.sku_id,
                location_id=shipment.destination_location_id,
                owner_org_id=shipment.owner_org_id,
                on_hand=shipment.quantity,
                reserved=0.0,
                blocked=0.0,
                confirmed_incoming=0.0,
                as_of_date=now.date(),
                created_at=now,
            )
            db.add(dest_inv)
        shipment.actual_delivery_date = now
        if shipment.actual_transport_cost is None:
            shipment.actual_transport_cost = shipment.estimated_transport_cost

    elif status_req.status == "cancelled" and prev_status == "ready_for_dispatch":
        # Roll back reservation
        inv_records = (
            db.query(InventorySnapshot)
            .filter(
                InventorySnapshot.sku_id == shipment.sku_id,
                InventorySnapshot.location_id == shipment.source_location_id,
            )
            .all()
        )
        rem = shipment.quantity
        for inv in inv_records:
            if inv.reserved > 0:
                unres = min(rem, float(inv.reserved))
                inv.reserved = max(0.0, float(inv.reserved - unres))
                rem -= unres
                if rem <= 0:
                    break

    shipment.status = status_req.status
    shipment.updated_at = now

    movement = StockMovement(
        movement_id=f"MOV-{uuid.uuid4().hex[:8].upper()}",
        shipment_id=shipment.shipment_id,
        sku_id=shipment.sku_id,
        source_location_id=shipment.source_location_id,
        destination_location_id=shipment.destination_location_id,
        quantity=shipment.quantity,
        movement_type=f"status_{status_req.status}",
        status=status_req.status,
        timestamp=now,
        notes=status_req.notes or f"Status transitioned to '{status_req.status}'.",
    )
    db.add(movement)

    audit_event = ShipmentEvent(
        event_id=f"EVT-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
        shipment_id=shipment.shipment_id,
        from_status=prev_status,
        to_status=status_req.status,
        actor_id="warehouse_logistics_operator",
        actor_role="operator",
        notes=status_req.notes or f"Transitioned to {status_req.status}",
        created_at=now,
    )
    db.add(audit_event)

    db.commit()
    db.refresh(shipment)
    return shipment
