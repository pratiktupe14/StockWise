"""Phase 4 Logistics Execution & Governance Service.

Manages the real-world operational lifecycle for StockWise shipments:
  Proposed -> Approved -> Ready for Dispatch -> In Transit -> Delivered
  (with Rejected and Cancelled exception states).

Enforces:
1. Strict state machine transitions (rejects invalid transitions).
2. Explicit authorized human recording of physical events (approval != physical dispatch).
3. Transactional inventory reservations and consumption (no double dispatch, no double deduction).
4. Immutable ShipmentEvent audit trail with actor IDs, roles, notes, and timestamps.
5. Bidirectional traceability linking shipments to Phase 3 Planning Runs & Decision Receipts.
6. Separation of estimated transport cost from actual transport cost in reporting currency (INR).
"""

import json
import uuid
from datetime import datetime, timezone, date
from typing import Optional, List, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models.entities import (
    Shipment,
    ShipmentEvent,
    StockMovement,
    InventorySnapshot,
    Location,
    Product,
    Organization,
    Route,
    PlanningRun,
    utcnow,
)
from app.services.idempotency_service import with_row_lock
from app.schemas.logistics import (
    ShipmentDispatchPrepareRequest,
    ShipmentDispatchConfirmRequest,
    ShipmentDeliveryConfirmRequest,
    ShipmentCarrierAssignRequest,
    ShipmentCarrierDecisionRequest,
    ShipmentExceptionRequest,
    ShipmentEventResponse,
    ShipmentTraceabilityResponse,
)

# Explicitly allowed lifecycle state transitions
ALLOWED_TRANSITIONS: Dict[str, set[str]] = {
    "proposed": {"approved", "rejected", "cancelled"},
    "approved": {"ready_for_dispatch", "cancelled"},
    "ready_for_dispatch": {"in_transit", "cancelled"},
    "in_transit": {"delivered"},
    "delivered": set(),    # Terminal state
    "rejected": set(),     # Terminal state
    "cancelled": set(),    # Terminal state
}


def create_shipment_event(
    db: Session,
    shipment_id: str,
    from_status: str,
    to_status: str,
    actor_id: str,
    actor_role: Optional[str] = None,
    notes: Optional[str] = None,
    metadata_dict: Optional[Dict[str, Any]] = None,
) -> ShipmentEvent:
    """Creates an immutable audit event for a shipment transition or coordination action."""
    now = utcnow()
    event_id = f"EVT-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    event = ShipmentEvent(
        event_id=event_id,
        shipment_id=shipment_id,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor_id,
        actor_role=actor_role or "system_operator",
        notes=notes,
        metadata_json=json.dumps(metadata_dict) if metadata_dict else None,
        created_at=now,
    )
    db.add(event)
    return event


def get_shipment_or_404(db: Session, shipment_id: str, for_update: bool = True) -> Shipment:
    query = db.query(Shipment).filter(Shipment.shipment_id == shipment_id)
    if for_update:
        query = with_row_lock(query, db)
    shipment = query.first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found.",
        )
    return shipment


def prepare_dispatch(
    db: Session,
    shipment_id: str,
    req: ShipmentDispatchPrepareRequest,
) -> Shipment:
    """
    Transitions an approved shipment into 'ready_for_dispatch'.
    - Validates shipment is in 'approved' status with row locking.
    - Validates source facility has sufficient unexpired dispatchable inventory.
    - Reserves the required units on unexpired batches in strict FEFO order.
    - Stores the dispatch preparation checklist.
    - Emits auditable ShipmentEvent and StockMovement.
    """
    shipment = get_shipment_or_404(db, shipment_id, for_update=True)

    if shipment.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"INVALID_STATE_TRANSITION: Cannot prepare dispatch for shipment '{shipment_id}' "
                f"with status '{shipment.status}'. Only 'approved' shipments can enter dispatch preparation."
            ),
        )

    # 1. Verify dispatchable inventory at source warehouse with row locks
    today = utcnow().date()
    inv_records = with_row_lock(
        db.query(InventorySnapshot).filter(
            InventorySnapshot.sku_id == shipment.sku_id,
            InventorySnapshot.location_id == shipment.source_location_id,
        ),
        db,
    ).all()

    # Sort FEFO: earliest expiry first, non-null before null
    inv_records.sort(
        key=lambda x: (
            0 if x.expiry_date is not None else 1,
            x.expiry_date or date.max,
            -x.dispatchable_stock,
            x.id or 0,
        )
    )

    # Filter out expired records
    unexpired_records = [
        rec for rec in inv_records
        if rec.expiry_date is None or rec.expiry_date > today
    ]

    total_dispatchable = sum(rec.dispatchable_stock for rec in unexpired_records)
    if total_dispatchable < shipment.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"INSUFFICIENT_STOCK_FOR_PREPARATION: Source facility has {total_dispatchable:.1f} "
                f"unexpired dispatchable units of SKU '{shipment.sku_id}', but shipment requires {shipment.quantity:.1f} units."
            ),
        )

    # 2. Reserve quantity across eligible unexpired batches in FEFO order
    remaining_to_reserve = shipment.quantity
    for inv in unexpired_records:
        available_in_rec = max(0.0, float(inv.on_hand - inv.reserved - inv.blocked))
        if available_in_rec > 0:
            reserve_amount = min(remaining_to_reserve, available_in_rec)
            inv.reserved += reserve_amount
            remaining_to_reserve -= reserve_amount
            if remaining_to_reserve <= 0:
                break

    now = utcnow()
    prev_status = shipment.status
    shipment.status = "ready_for_dispatch"
    shipment.dispatch_checklist = json.dumps(req.checklist_items)
    shipment.updated_at = now

    # 3. Create StockMovement
    movement = StockMovement(
        movement_id=f"MOV-{uuid.uuid4().hex[:8].upper()}",
        shipment_id=shipment.shipment_id,
        sku_id=shipment.sku_id,
        source_location_id=shipment.source_location_id,
        destination_location_id=shipment.destination_location_id,
        quantity=shipment.quantity,
        movement_type="dispatch_preparation_reservation",
        status="ready_for_dispatch",
        timestamp=now,
        notes=f"Reserved {shipment.quantity} units for dispatch staging. Checklist: {', '.join(req.checklist_items)}",
    )
    db.add(movement)

    # 4. Create immutable ShipmentEvent
    create_shipment_event(
        db=db,
        shipment_id=shipment.shipment_id,
        from_status=prev_status,
        to_status="ready_for_dispatch",
        actor_id=req.authorized_user_id,
        actor_role=req.actor_role,
        notes=req.notes or f"Dispatch checklist verified ({len(req.checklist_items)} items passed).",
        metadata_dict={"checklist": req.checklist_items},
    )

    db.commit()
    db.refresh(shipment)
    return shipment


def confirm_dispatch(
    db: Session,
    shipment_id: str,
    req: ShipmentDispatchConfirmRequest,
) -> Shipment:
    """
    Records explicit physical dispatch event by an authorized warehouse user.
    - Transitions shipment from 'ready_for_dispatch' to 'in_transit'.
    - Consumes physical inventory from source facility: decrements on_hand and clears reserved.
    - Records carrier details (consignment number, vehicle number, driver contact).
    - Prevents duplicate dispatch (idempotency/lock).
    - Emits StockMovement(movement_type='actual_dispatch') and ShipmentEvent.
    """
    shipment = get_shipment_or_404(db, shipment_id)

    if shipment.status == "in_transit":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DUPLICATE_DISPATCH_REJECTED: Shipment '{shipment_id}' has already been dispatched into transit.",
        )

    if shipment.status != "ready_for_dispatch":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"INVALID_STATE_TRANSITION: Cannot dispatch shipment '{shipment_id}' "
                f"from status '{shipment.status}'. Shipment must be 'ready_for_dispatch' before actual dispatch."
            ),
        )

    # 1. Deduct physical stock from source facility and release reservation in FEFO order
    inv_records = with_row_lock(
        db.query(InventorySnapshot).filter(
            InventorySnapshot.sku_id == shipment.sku_id,
            InventorySnapshot.location_id == shipment.source_location_id,
        ),
        db,
    ).all()

    # Sort FEFO: earliest expiry first, non-null before null
    inv_records.sort(
        key=lambda x: (
            0 if x.expiry_date is not None else 1,
            x.expiry_date or date.max,
            -x.dispatchable_stock,
            x.id or 0,
        )
    )

    remaining_to_deduct = shipment.quantity
    for inv in inv_records:
        if inv.on_hand > 0:
            deduct_amount = min(remaining_to_deduct, float(inv.on_hand))
            inv.on_hand = max(0.0, float(inv.on_hand - deduct_amount))
            inv.reserved = max(0.0, float(inv.reserved - deduct_amount))
            remaining_to_deduct -= deduct_amount
            if remaining_to_deduct <= 0:
                break

    now = utcnow()
    prev_status = shipment.status
    shipment.status = "in_transit"
    if req.consignment_number:
        shipment.consignment_number = req.consignment_number.strip()
    if req.vehicle_number:
        shipment.vehicle_number = req.vehicle_number.strip()
    if req.driver_contact:
        shipment.driver_contact = req.driver_contact.strip()
    shipment.actual_pickup_date = req.actual_pickup_date or now
    shipment.updated_at = now

    # 2. Record physical stock deduction movement
    movement = StockMovement(
        movement_id=f"MOV-{uuid.uuid4().hex[:8].upper()}",
        shipment_id=shipment.shipment_id,
        sku_id=shipment.sku_id,
        source_location_id=shipment.source_location_id,
        destination_location_id=shipment.destination_location_id,
        quantity=shipment.quantity,
        movement_type="actual_dispatch",
        status="in_transit",
        timestamp=now,
        notes=(
            f"Physical dispatch confirmed by {req.authorized_user_id}. "
            f"Consignment: {shipment.consignment_number or 'N/A'}, Vehicle: {shipment.vehicle_number or 'N/A'}."
        ),
    )
    db.add(movement)

    # 3. Create immutable ShipmentEvent
    create_shipment_event(
        db=db,
        shipment_id=shipment.shipment_id,
        from_status=prev_status,
        to_status="in_transit",
        actor_id=req.authorized_user_id,
        actor_role=req.actor_role,
        notes=req.notes or f"Dispatched with vehicle {shipment.vehicle_number or 'N/A'}",
        metadata_dict={
            "consignment_number": shipment.consignment_number,
            "vehicle_number": shipment.vehicle_number,
            "driver_contact": shipment.driver_contact,
            "actual_pickup_date": shipment.actual_pickup_date.isoformat(),
        },
    )

    db.commit()
    db.refresh(shipment)
    return shipment


def confirm_delivery(
    db: Session,
    shipment_id: str,
    req: ShipmentDeliveryConfirmRequest,
) -> Shipment:
    """
    Records explicit delivery confirmation by an authorized receiving user.
    - Transitions shipment from 'in_transit' to 'delivered'.
    - Credits physical inventory at destination facility.
    - Records actual delivery timestamp, actual freight cost (in INR), and POD reference.
    - Rejects duplicate confirmation safely (idempotent / locked).
    - Emits StockMovement(movement_type='actual_delivery') and ShipmentEvent.
    """
    shipment = get_shipment_or_404(db, shipment_id)

    if shipment.status == "delivered":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DUPLICATE_DELIVERY_REJECTED: Shipment '{shipment_id}' has already been confirmed as delivered.",
        )

    if shipment.status != "in_transit":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"INVALID_STATE_TRANSITION: Cannot confirm delivery for shipment '{shipment_id}' "
                f"with status '{shipment.status}'. Shipment must be 'in_transit' before delivery confirmation."
            ),
        )

    now = utcnow()

    # 1. Credit stock to destination facility
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
        # Create an inventory record for newly received SKU at destination
        dest_inv = InventorySnapshot(
            snapshot_id=f"SNAP-RECEIVE-{now.strftime('%Y%m%d')}",
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

    prev_status = shipment.status
    shipment.status = "delivered"
    shipment.actual_delivery_date = req.actual_delivery_date or now
    if req.actual_transport_cost is not None:
        shipment.actual_transport_cost = float(req.actual_transport_cost)
    else:
        shipment.actual_transport_cost = shipment.estimated_transport_cost

    if req.pod_reference:
        shipment.pod_reference = req.pod_reference.strip()
    shipment.updated_at = now

    # 2. Record physical delivery movement
    movement = StockMovement(
        movement_id=f"MOV-{uuid.uuid4().hex[:8].upper()}",
        shipment_id=shipment.shipment_id,
        sku_id=shipment.sku_id,
        source_location_id=shipment.source_location_id,
        destination_location_id=shipment.destination_location_id,
        quantity=shipment.quantity,
        movement_type="actual_delivery",
        status="delivered",
        timestamp=now,
        notes=(
            f"Delivery received and verified at {shipment.destination_location_id} by {req.authorized_user_id}. "
            f"POD Ref: {shipment.pod_reference or 'N/A'}. Actual Freight: ₹{shipment.actual_transport_cost:.2f}."
        ),
    )
    db.add(movement)

    # 3. Create immutable ShipmentEvent
    create_shipment_event(
        db=db,
        shipment_id=shipment.shipment_id,
        from_status=prev_status,
        to_status="delivered",
        actor_id=req.authorized_user_id,
        actor_role=req.actor_role,
        notes=req.notes or f"Delivery confirmed. POD: {shipment.pod_reference or 'N/A'}",
        metadata_dict={
            "actual_delivery_date": shipment.actual_delivery_date.isoformat(),
            "actual_transport_cost": shipment.actual_transport_cost,
            "pod_reference": shipment.pod_reference,
        },
    )

    db.commit()
    db.refresh(shipment)
    return shipment


def assign_carrier(
    db: Session,
    shipment_id: str,
    req: ShipmentCarrierAssignRequest,
) -> Shipment:
    """
    Coordinates logistics agency assignment for an approved or in-preparation shipment.
    """
    shipment = get_shipment_or_404(db, shipment_id)

    if shipment.status in {"delivered", "cancelled", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assign carrier to shipment '{shipment_id}' in terminal state '{shipment.status}'.",
        )

    carrier_org = db.query(Organization).filter(Organization.org_id == req.carrier_agency_id).first()
    if not carrier_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Carrier organization '{req.carrier_agency_id}' not found.",
        )

    now = utcnow()
    shipment.carrier_agency_id = req.carrier_agency_id
    if req.carrier_contact:
        shipment.carrier_contact = req.carrier_contact.strip()
    if req.planned_pickup_date:
        shipment.planned_pickup_date = req.planned_pickup_date
    if req.estimated_arrival_date:
        shipment.estimated_arrival_date = req.estimated_arrival_date
    shipment.logistics_status = "assigned"
    shipment.updated_at = now

    create_shipment_event(
        db=db,
        shipment_id=shipment.shipment_id,
        from_status=shipment.status,
        to_status=shipment.status,
        actor_id=req.authorized_user_id,
        actor_role=req.actor_role,
        notes=req.notes or f"Assigned carrier '{carrier_org.name}' ({req.carrier_agency_id})",
        metadata_dict={
            "action": "carrier_assigned",
            "carrier_agency_id": req.carrier_agency_id,
            "carrier_contact": shipment.carrier_contact,
        },
    )

    db.commit()
    db.refresh(shipment)
    return shipment


def decide_carrier_assignment(
    db: Session,
    shipment_id: str,
    req: ShipmentCarrierDecisionRequest,
) -> Shipment:
    """
    Records logistics agency coordinator's acceptance or rejection of a shipment allocation.
    """
    shipment = get_shipment_or_404(db, shipment_id)

    if shipment.status in {"delivered", "cancelled", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot record carrier decision for shipment in terminal state '{shipment.status}'.",
        )

    now = utcnow()
    if req.accepted:
        shipment.logistics_status = "accepted"
        if req.consignment_number:
            shipment.consignment_number = req.consignment_number.strip()
        if req.vehicle_number:
            shipment.vehicle_number = req.vehicle_number.strip()
        if req.driver_contact:
            shipment.driver_contact = req.driver_contact.strip()
        decision_label = "accepted"
    else:
        shipment.logistics_status = "rejected"
        decision_label = "rejected"

    shipment.logistics_notes = req.notes
    shipment.updated_at = now

    create_shipment_event(
        db=db,
        shipment_id=shipment.shipment_id,
        from_status=shipment.status,
        to_status=shipment.status,
        actor_id=req.authorized_user_id,
        actor_role=req.actor_role,
        notes=f"Logistics provider {decision_label} shipment assignment. Notes: {req.notes or 'None'}",
        metadata_dict={
            "action": f"carrier_{decision_label}",
            "consignment_number": shipment.consignment_number,
            "vehicle_number": shipment.vehicle_number,
        },
    )

    db.commit()
    db.refresh(shipment)
    return shipment


def record_exception(
    db: Session,
    shipment_id: str,
    req: ShipmentExceptionRequest,
) -> Shipment:
    """
    Records delay, breakdown, weather event, or dock congestion notes without corrupting lifecycle state.
    """
    shipment = get_shipment_or_404(db, shipment_id)

    now = utcnow()
    shipment.exception_reason = req.exception_reason.strip()
    shipment.exception_notes = req.notes
    shipment.updated_at = now

    create_shipment_event(
        db=db,
        shipment_id=shipment.shipment_id,
        from_status=shipment.status,
        to_status=shipment.status,
        actor_id=req.authorized_user_id,
        actor_role=req.actor_role,
        notes=f"OPERATIONAL_EXCEPTION: {req.exception_reason}. Narrative: {req.notes or 'N/A'}",
        metadata_dict={
            "action": "exception_logged",
            "exception_reason": req.exception_reason,
            "exception_notes": req.notes,
        },
    )

    db.commit()
    db.refresh(shipment)
    return shipment


def cancel_shipment(
    db: Session,
    shipment_id: str,
    authorized_user_id: str,
    actor_role: Optional[str] = "operations_manager",
    notes: Optional[str] = None,
) -> Shipment:
    """
    Cancels a proposed, approved, or ready_for_dispatch shipment and rolls back any reserved stock.
    In-transit or delivered shipments cannot be cancelled.
    """
    shipment = get_shipment_or_404(db, shipment_id)

    if shipment.status in {"in_transit", "delivered"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel shipment '{shipment_id}' that is already '{shipment.status}'.",
        )

    if shipment.status == "cancelled":
        return shipment

    # If it was ready_for_dispatch, release the reserved stock
    if shipment.status == "ready_for_dispatch":
        inv_records = with_row_lock(
            db.query(InventorySnapshot).filter(
                InventorySnapshot.sku_id == shipment.sku_id,
                InventorySnapshot.location_id == shipment.source_location_id,
            ),
            db,
        ).all()
        remaining_to_unreserve = shipment.quantity
        for inv in inv_records:
            if inv.reserved > 0:
                unreserve_amount = min(remaining_to_unreserve, float(inv.reserved))
                inv.reserved = max(0.0, float(inv.reserved - unreserve_amount))
                remaining_to_unreserve -= unreserve_amount
                if remaining_to_unreserve <= 0:
                    break

    now = utcnow()
    prev_status = shipment.status
    shipment.status = "cancelled"
    shipment.updated_at = now

    movement = StockMovement(
        movement_id=f"MOV-{uuid.uuid4().hex[:8].upper()}",
        shipment_id=shipment.shipment_id,
        sku_id=shipment.sku_id,
        source_location_id=shipment.source_location_id,
        destination_location_id=shipment.destination_location_id,
        quantity=shipment.quantity,
        movement_type="cancellation_reversal",
        status="cancelled",
        timestamp=now,
        notes=f"Shipment cancelled by {authorized_user_id}. {notes or ''}",
    )
    db.add(movement)

    create_shipment_event(
        db=db,
        shipment_id=shipment.shipment_id,
        from_status=prev_status,
        to_status="cancelled",
        actor_id=authorized_user_id,
        actor_role=actor_role,
        notes=notes or "Shipment cancelled before dispatch.",
    )

    db.commit()
    db.refresh(shipment)
    return shipment


def get_shipment_events(db: Session, shipment_id: str) -> List[ShipmentEvent]:
    """Returns chronological audit trail of events for a shipment."""
    get_shipment_or_404(db, shipment_id)
    return (
        db.query(ShipmentEvent)
        .filter(ShipmentEvent.shipment_id == shipment_id)
        .order_by(desc(ShipmentEvent.created_at))
        .all()
    )


def get_shipment_traceability(db: Session, shipment_id: str) -> ShipmentTraceabilityResponse:
    """
    Constructs full end-to-end traceability for a shipment:
    - Base shipment details.
    - Associated Phase 3 Planning Run metadata (if originating from optimizer).
    - Original Decision Receipt evidence & rationale.
    - Complete immutable ShipmentEvent audit history.
    - Complete StockMovement audit trail.
    - Separation of estimated vs actual transport costs.
    """
    shipment = get_shipment_or_404(db, shipment_id)

    # 1. Look up planning run & decision receipt
    planning_run_meta = None
    matched_receipt = None
    rationale = None

    if shipment.planning_run_id:
        pr = db.query(PlanningRun).filter(PlanningRun.run_id == shipment.planning_run_id).first()
        if pr:
            planning_run_meta = {
                "run_id": pr.run_id,
                "snapshot_id": pr.snapshot_id,
                "horizon_days": pr.horizon_days,
                "objective_strategy": pr.objective_strategy,
                "solver_status": pr.solver_status,
                "solve_time_ms": pr.solve_time_ms,
                "service_level_percent": pr.service_level_percent,
                "created_at": pr.created_at.isoformat(),
            }
            if pr.decision_receipts:
                try:
                    receipts = json.loads(pr.decision_receipts)
                    for r in receipts:
                        # Match receipt by shipment_id or SKU + source + destination
                        if (
                            r.get("shipment_id") == shipment_id
                            or (
                                r.get("sku_id") == shipment.sku_id
                                and r.get("source_location_id") == shipment.source_location_id
                                and r.get("destination_location_id") == shipment.destination_location_id
                            )
                        ):
                            matched_receipt = r
                            rationale = r.get("decision_rationale")
                            break
                except Exception:
                    pass

    # 2. Gather events
    events = (
        db.query(ShipmentEvent)
        .filter(ShipmentEvent.shipment_id == shipment_id)
        .order_by(desc(ShipmentEvent.created_at))
        .all()
    )
    event_responses = [
        ShipmentEventResponse(
            event_id=e.event_id,
            shipment_id=e.shipment_id,
            from_status=e.from_status,
            to_status=e.to_status,
            actor_id=e.actor_id,
            actor_role=e.actor_role,
            notes=e.notes,
            metadata_json=e.metadata_json,
            created_at=e.created_at,
        )
        for e in events
    ]

    # 3. Gather stock movements
    movements = (
        db.query(StockMovement)
        .filter(StockMovement.shipment_id == shipment_id)
        .order_by(desc(StockMovement.timestamp))
        .all()
    )
    movement_dicts = [
        {
            "movement_id": m.movement_id,
            "sku_id": m.sku_id,
            "source_location_id": m.source_location_id,
            "destination_location_id": m.destination_location_id,
            "quantity": m.quantity,
            "movement_type": m.movement_type,
            "status": m.status,
            "timestamp": m.timestamp.isoformat(),
            "notes": m.notes,
        }
        for m in movements
    ]

    return ShipmentTraceabilityResponse(
        shipment_id=shipment.shipment_id,
        sku_id=shipment.sku_id,
        product_name=shipment.product.name if shipment.product else shipment.sku_id,
        quantity=shipment.quantity,
        source_location_id=shipment.source_location_id,
        source_location_name=shipment.source_location.name if shipment.source_location else shipment.source_location_id,
        destination_location_id=shipment.destination_location_id,
        destination_location_name=shipment.destination_location.name if shipment.destination_location else shipment.destination_location_id,
        owner_org_id=shipment.owner_org_id,
        owner_org_name=shipment.owner_org.name if shipment.owner_org else None,
        carrier_agency_id=shipment.carrier_agency_id,
        carrier_agency_name=shipment.carrier_agency.name if shipment.carrier_agency else None,
        carrier_contact=shipment.carrier_contact,
        route_id=shipment.route_id,
        lead_time_days=shipment.route.lead_time_days if shipment.route else None,
        currency="INR",
        estimated_transport_cost=shipment.estimated_transport_cost,
        actual_transport_cost=shipment.actual_transport_cost,
        status=shipment.status,
        approval_status=shipment.approval_status,
        approved_by=shipment.approved_by,
        approval_notes=shipment.approval_notes,
        logistics_status=shipment.logistics_status,
        consignment_number=shipment.consignment_number,
        vehicle_number=shipment.vehicle_number,
        driver_contact=shipment.driver_contact,
        planned_pickup_date=shipment.planned_pickup_date,
        actual_pickup_date=shipment.actual_pickup_date,
        actual_delivery_date=shipment.actual_delivery_date,
        exception_reason=shipment.exception_reason,
        exception_notes=shipment.exception_notes,
        pod_reference=shipment.pod_reference,
        dispatch_checklist=shipment.dispatch_checklist,
        planning_run_id=shipment.planning_run_id,
        decision_rationale=rationale,
        planning_run_metadata=planning_run_meta,
        decision_receipt=matched_receipt,
        created_at=shipment.created_at,
        updated_at=shipment.updated_at,
        events=event_responses,
        movements=movement_dicts,
    )
