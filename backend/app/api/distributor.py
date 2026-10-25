import uuid
from datetime import datetime, timezone, date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.core.database import get_db
from app.models.entities import (
    InventorySnapshot,
    Location,
    Product,
    Shipment,
    StockMovement,
    ShipmentEvent,
    Organization,
)
from app.schemas.entities import InventoryRecordResponse
from app.schemas.network import ShipmentResponse
from app.schemas.distributor import (
    DistributorDashboardResponse,
    DistributorRequestCreatePayload,
    DistributorDeliveryConfirmPayload,
    DistributorRequestCancelPayload,
)

from app.api.shipments import map_shipment_response
from app.core.security import AuthenticatedUser, require_roles
from app.services.expiry_service import calculate_batch_expiry_risk

router = APIRouter(prefix="/distributor", tags=["Distributor Portal"])


def get_distributor_org_id(current_user: AuthenticatedUser, requested_org_id: Optional[str] = None) -> str:
    """
    Resolves the effective distributor organization identifier.
    - Company Admin: May inspect a specific distributor org or defaults to 'ORG-DIST-WEST'.
    - Distributor: Strictly constrained to their own verified server-assigned org_id.
    - Any attempt by non-admins to specify a different organization is forbidden (HTTP 403).
    """
    if current_user.role == "admin":
        if requested_org_id and requested_org_id.strip():
            return requested_org_id.strip()
        if not current_user.org_id or current_user.org_id.startswith("ORG-FMCG"):
            return "ORG-DIST-WEST"
        return current_user.org_id

    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User identity has no associated organization identifier.",
        )

    if requested_org_id and requested_org_id.strip() != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You are not authorized to access organization '{requested_org_id}'.",
        )

    return current_user.org_id


@router.get(
    "/dashboard",
    response_model=DistributorDashboardResponse,
    summary="Get distributor operational dashboard and KPI summary",
)
def get_distributor_dashboard(
    distributor_org_id: Optional[str] = Query(None, description="Distributor organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "distributor"])),
):
    """
    Returns distributor-owned inventory metrics, pending replenishment requests,
    active incoming shipments, and near-expiry risk counts.
    Strictly isolated to user's authorized organization.
    """
    org_id = get_distributor_org_id(current_user, distributor_org_id)

    # 1. Inventory Owned by Distributor
    inv_records = (
        db.query(InventorySnapshot, Product, Location, Organization)
        .outerjoin(Product, InventorySnapshot.sku_id == Product.sku_id)
        .outerjoin(Location, InventorySnapshot.location_id == Location.location_id)
        .outerjoin(Organization, InventorySnapshot.owner_org_id == Organization.org_id)
        .filter(InventorySnapshot.owner_org_id == org_id)
        .all()
    )

    total_on_hand = sum(inv.on_hand for inv, _, _, _ in inv_records)
    total_dispatchable = sum(inv.dispatchable_stock for inv, _, _, _ in inv_records)
    distinct_skus = len(set(inv.sku_id for inv, _, _, _ in inv_records))

    today = date.today()
    near_expiry_count = 0
    for inv, _, _, _ in inv_records:
        risk = calculate_batch_expiry_risk(inv, as_of=today)
        if risk["risk_category"] in ("critical", "high", "medium"):
            near_expiry_count += 1

    # 2. Pending Stock Requests submitted by Distributor
    pending_req_query = (
        db.query(Shipment)
        .filter(
            Shipment.owner_org_id == org_id,
            Shipment.planning_run_id.like("DIST-REQ%"),
            Shipment.approval_status == "pending",
        )
        .order_by(desc(Shipment.created_at))
    )
    pending_requests = pending_req_query.all()

    # 3. Shipments in Transit to / belonging to Distributor
    # Find locations owned/operated by distributor
    dist_loc_ids = [
        l.location_id
        for l in db.query(Location)
        .filter(or_(Location.owner_org_id == org_id, Location.operator_org_id == org_id))
        .all()
    ]

    shipment_query = (
        db.query(Shipment)
        .filter(
            or_(
                Shipment.owner_org_id == org_id,
                Shipment.destination_location_id.in_(dist_loc_ids) if dist_loc_ids else False,
            )
        )
        .order_by(desc(Shipment.created_at))
    )
    all_shipments = shipment_query.all()
    in_transit_count = sum(1 for s in all_shipments if s.status == "in_transit")

    return DistributorDashboardResponse(
        distributor_org_id=org_id,
        total_owned_skus=distinct_skus,
        total_on_hand_units=round(total_on_hand, 2),
        total_dispatchable_units=round(total_dispatchable, 2),
        pending_requests_count=len(pending_requests),
        in_transit_shipments_count=in_transit_count,
        near_expiry_batches_count=near_expiry_count,
        recent_shipments=[map_shipment_response(s) for s in all_shipments[:10]],
        recent_requests=[map_shipment_response(r) for r in pending_requests[:10]],
    )


@router.get(
    "/inventory",
    response_model=List[InventoryRecordResponse],
    summary="List distributor's owned inventory and batch status",
)
def get_distributor_inventory(
    sku_id: Optional[str] = None,
    location_id: Optional[str] = None,
    distributor_org_id: Optional[str] = Query(None, description="Distributor organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "distributor"])),
):
    """
    Returns inventory snapshots legally owned by the distributor.
    Does not expose other distributors' inventory or confidential company stock.
    """
    org_id = get_distributor_org_id(current_user, distributor_org_id)

    query = (
        db.query(InventorySnapshot, Product, Location, Organization)
        .outerjoin(Product, InventorySnapshot.sku_id == Product.sku_id)
        .outerjoin(Location, InventorySnapshot.location_id == Location.location_id)
        .outerjoin(Organization, InventorySnapshot.owner_org_id == Organization.org_id)
        .filter(InventorySnapshot.owner_org_id == org_id)
        .order_by(InventorySnapshot.sku_id.asc())
    )

    if sku_id:
        query = query.filter(InventorySnapshot.sku_id == sku_id.strip())
    if location_id:
        query = query.filter(InventorySnapshot.location_id == location_id.strip())

    results = query.all()
    records = []
    for inv, prod, loc, org in results:
        records.append(
            InventoryRecordResponse(
                id=inv.id,
                snapshot_id=inv.snapshot_id,
                sku_id=inv.sku_id,
                product_name=prod.name if prod else None,
                category=prod.category if prod else None,
                unit=prod.unit if prod else "cases",
                location_id=inv.location_id,
                location_name=loc.name if loc else None,
                region=loc.region if loc else None,
                on_hand=inv.on_hand,
                reserved=inv.reserved,
                blocked=inv.blocked,
                confirmed_incoming=inv.confirmed_incoming,
                dispatchable_stock=inv.dispatchable_stock,
                as_of_date=inv.as_of_date,
                owner_org_id=inv.owner_org_id,
                owner_org_name=org.name if org else None,
                batch_number=inv.batch_number,
                expiry_date=inv.expiry_date,
                created_at=inv.created_at,
            )
        )
    return records


@router.get(
    "/requests",
    response_model=List[ShipmentResponse],
    summary="List stock and transfer requests submitted by the distributor",
)
def get_distributor_requests(
    distributor_org_id: Optional[str] = Query(None, description="Distributor organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "distributor"])),
):
    """
    Returns all stock replenishment requests submitted by the authenticated distributor.
    """
    org_id = get_distributor_org_id(current_user, distributor_org_id)
    requests = (
        db.query(Shipment)
        .filter(
            Shipment.owner_org_id == org_id,
            Shipment.planning_run_id.like("DIST-REQ%"),
        )
        .order_by(desc(Shipment.created_at))
        .all()
    )
    return [map_shipment_response(r) for r in requests]


@router.post(
    "/requests",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new distributor replenishment or transfer request",
)
def submit_distributor_request(
    payload: DistributorRequestCreatePayload,
    distributor_org_id: Optional[str] = Query(None, description="Distributor organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "distributor"])),
):
    """
    Submits a new stock replenishment request for the distributor.
    - Validates positive requested quantity.
    - Persists request in 'proposed' state with approval_status 'pending'.
    - Logs audit StockMovement(movement_type='distributor_request').
    - DOES NOT directly alter physical stock, commit reservations, or auto-dispatch.
    """
    org_id = get_distributor_org_id(current_user, distributor_org_id)

    if payload.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requested quantity must be strictly greater than 0.",
        )

    # Validate SKU exists
    prod = db.query(Product).filter(Product.sku_id == payload.sku_id.strip()).first()
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with SKU '{payload.sku_id}' not found.",
        )

    # Resolve destination location: if not specified, find a location owned/operated by distributor
    dest_loc = payload.destination_location_id
    if not dest_loc:
        loc = (
            db.query(Location)
            .filter(or_(Location.owner_org_id == org_id, Location.operator_org_id == org_id))
            .first()
        )
        dest_loc = loc.location_id if loc else "LOC-DIST-DEFAULT"

    src_loc = payload.source_location_id or "LOC-WH-CENTRAL"
    req_id = f"REQ-DIST-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    planning_id = f"DIST-REQ-{uuid.uuid4().hex[:6].upper()}"

    notes_str = f"DISTRIBUTOR_REQUEST: {payload.reason or 'Replenishment'}. Note: {payload.notes or 'None'}"

    shipment = Shipment(
        shipment_id=req_id,
        sku_id=payload.sku_id.strip(),
        quantity=float(payload.quantity),
        source_location_id=src_loc,
        destination_location_id=dest_loc,
        owner_org_id=org_id,
        status="proposed",
        planning_run_id=planning_id,
        approval_status="pending",
        approval_notes=notes_str,
    )
    db.add(shipment)

    # Add audit movement
    mov = StockMovement(
        movement_id=f"MOV-{uuid.uuid4().hex[:8].upper()}",
        shipment_id=req_id,
        sku_id=payload.sku_id.strip(),
        source_location_id=src_loc,
        destination_location_id=dest_loc,
        quantity=float(payload.quantity),
        movement_type="distributor_request",
        status="proposed",
        timestamp=datetime.now(timezone.utc),
        notes=notes_str,
    )
    db.add(mov)

    # Add shipment event
    evt = ShipmentEvent(
        event_id=f"EVT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
        shipment_id=req_id,
        from_status="none",
        to_status="proposed",
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        notes="Distributor stock replenishment request submitted",
    )
    db.add(evt)

    db.commit()
    db.refresh(shipment)
    return map_shipment_response(shipment)


@router.get(
    "/shipments",
    response_model=List[ShipmentResponse],
    summary="List shipments authorized for the distributor",
)
def get_distributor_shipments(
    status_filter: Optional[str] = Query(None, description="Optional status filter"),
    distributor_org_id: Optional[str] = Query(None, description="Distributor organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "distributor"])),
):
    """
    Returns only shipments belonging to or destined for the distributor.
    """
    org_id = get_distributor_org_id(current_user, distributor_org_id)

    dist_loc_ids = [
        l.location_id
        for l in db.query(Location)
        .filter(or_(Location.owner_org_id == org_id, Location.operator_org_id == org_id))
        .all()
    ]

    query = db.query(Shipment).filter(
        or_(
            Shipment.owner_org_id == org_id,
            Shipment.destination_location_id.in_(dist_loc_ids) if dist_loc_ids else False,
        )
    ).order_by(desc(Shipment.created_at))

    if status_filter:
        query = query.filter(Shipment.status == status_filter.strip().lower())

    shipments = query.all()
    return [map_shipment_response(s) for s in shipments]


@router.post(
    "/shipments/{shipment_id}/confirm-receipt",
    response_model=ShipmentResponse,
    summary="Confirm received shipment quantity and report discrepancies",
)
def confirm_distributor_receipt(
    shipment_id: str,
    payload: DistributorDeliveryConfirmPayload,
    distributor_org_id: Optional[str] = Query(None, description="Distributor organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "distributor"])),
):
    """
    Confirms physical delivery receipt for a shipment in transit to the distributor.
    - Validates caller belongs to recipient organization.
    - Captures actual received quantity and condition status (intact, shortage, damaged, excess).
    - Prevents duplicate receipt confirmation.
    - Credits physical inventory snapshot at distributor facility.
    - Logs auditable StockMovement and ShipmentEvent with user attribution.
    - Transitions shipment status to 'delivered'.
    """
    org_id = get_distributor_org_id(current_user, distributor_org_id)

    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id.strip()).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID '{shipment_id}' not found.",
        )

    # Check recipient authorization
    dist_loc_ids = [
        l.location_id
        for l in db.query(Location)
        .filter(or_(Location.owner_org_id == org_id, Location.operator_org_id == org_id))
        .all()
    ]
    is_dest = shipment.destination_location_id in dist_loc_ids
    is_owner = shipment.owner_org_id == org_id

    if current_user.role != "admin" and not (is_dest or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You are not authorized to confirm receipt for shipments destined to another organization.",
        )

    # Prevent duplicate receipt
    if shipment.status == "delivered":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DUPLICATE_RECEIPT_REJECTED: Shipment '{shipment_id}' has already been confirmed as delivered.",
        )

    if shipment.status != "in_transit":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"INVALID_STATE_TRANSITION: Cannot confirm receipt for shipment '{shipment_id}' "
                f"with status '{shipment.status}'. Shipment must be 'in_transit' before delivery confirmation."
            ),
        )

    if payload.received_quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Received quantity cannot be negative.",
        )

    now = datetime.now(timezone.utc)

    # Credit stock to destination facility owned by distributor
    dest_inv = (
        db.query(InventorySnapshot)
        .filter(
            InventorySnapshot.sku_id == shipment.sku_id,
            InventorySnapshot.location_id == shipment.destination_location_id,
            InventorySnapshot.owner_org_id == org_id,
        )
        .first()
    )

    if dest_inv:
        dest_inv.on_hand += float(payload.received_quantity)
    else:
        dest_inv = InventorySnapshot(
            snapshot_id=f"SNAP-DIST-REC-{now.strftime('%Y%m%d')}",
            sku_id=shipment.sku_id,
            location_id=shipment.destination_location_id,
            owner_org_id=org_id,
            on_hand=float(payload.received_quantity),
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            as_of_date=now.date(),
            created_at=now,
        )
        db.add(dest_inv)

    # Update shipment
    shipment.status = "delivered"
    shipment.actual_delivery_date = now
    discrepancy_str = f"Receipt confirmed: {payload.received_quantity}/{shipment.quantity} units. Condition: {payload.condition_status}."
    if payload.discrepancy_units and payload.discrepancy_units > 0:
        discrepancy_str += f" Discrepancy: {payload.discrepancy_units} units."
    if payload.notes:
        discrepancy_str += f" Notes: {payload.notes}"

    if payload.condition_status != "intact" or (payload.discrepancy_units and payload.discrepancy_units > 0):
        shipment.exception_notes = discrepancy_str

    # Create immutable audit movement
    mov = StockMovement(
        movement_id=f"MOV-DREC-{uuid.uuid4().hex[:8].upper()}",
        shipment_id=shipment.shipment_id,
        sku_id=shipment.sku_id,
        source_location_id=shipment.source_location_id,
        destination_location_id=shipment.destination_location_id,
        quantity=float(payload.received_quantity),
        movement_type="distributor_receipt",
        status="delivered",
        timestamp=now,
        notes=discrepancy_str,
    )
    db.add(mov)

    # Create immutable ShipmentEvent
    evt = ShipmentEvent(
        event_id=f"EVT-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
        shipment_id=shipment.shipment_id,
        from_status="in_transit",
        to_status="delivered",
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        notes=discrepancy_str,
    )
    db.add(evt)

    db.commit()
    db.refresh(shipment)
    return map_shipment_response(shipment)


@router.post(
    "/requests/{shipment_id}/cancel",
    response_model=ShipmentResponse,
    summary="Cancel a pending replenishment request",
)
def cancel_distributor_request(
    shipment_id: str,
    payload: DistributorRequestCancelPayload,
    distributor_org_id: Optional[str] = Query(None, description="Distributor organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "distributor"])),
):
    """
    Cancels a pending replenishment request.
    Only permitted when approval_status is 'pending' and shipment is 'proposed'.
    """
    org_id = get_distributor_org_id(current_user, distributor_org_id)

    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id.strip()).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Replenishment request '{shipment_id}' not found.",
        )

    if current_user.role != "admin" and shipment.owner_org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot cancel a request submitted by another organization.",
        )

    if shipment.approval_status != "pending" or shipment.status != "proposed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"CANNOT_CANCEL_REQUEST: Request '{shipment_id}' cannot be cancelled because "
                f"it is currently '{shipment.status}' with approval status '{shipment.approval_status}'."
            ),
        )

    now = datetime.now(timezone.utc)
    cancel_reason = payload.reason or "Cancelled by distributor."

    shipment.status = "cancelled"
    shipment.approval_status = "rejected"
    shipment.approval_notes = f"CANCELLED: {cancel_reason}"

    # Audit movement
    mov = StockMovement(
        movement_id=f"MOV-DCAN-{uuid.uuid4().hex[:8].upper()}",
        shipment_id=shipment.shipment_id,
        sku_id=shipment.sku_id,
        source_location_id=shipment.source_location_id,
        destination_location_id=shipment.destination_location_id,
        quantity=shipment.quantity,
        movement_type="distributor_cancellation",
        status="cancelled",
        timestamp=now,
        notes=f"Cancelled by user: {cancel_reason}",
    )
    db.add(mov)

    # Shipment event
    evt = ShipmentEvent(
        event_id=f"EVT-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
        shipment_id=shipment.shipment_id,
        from_status="proposed",
        to_status="cancelled",
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        notes=f"Distributor replenishment request cancelled. Reason: {cancel_reason}",
    )
    db.add(evt)

    db.commit()
    db.refresh(shipment)
    return map_shipment_response(shipment)

