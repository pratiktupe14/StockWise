import uuid
from datetime import datetime, timezone, date
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
from app.schemas.retailer import (
    RetailerDashboardResponse,
    RetailerRequestCreatePayload,
    RetailerDeliveryConfirmPayload,
    RetailerRequestCancelPayload,
)

from app.api.shipments import map_shipment_response
from app.core.security import AuthenticatedUser, require_roles
from app.services.expiry_service import calculate_batch_expiry_risk

router = APIRouter(prefix="/retailer", tags=["Retail Shop Portal"])


def get_retailer_org_id(current_user: AuthenticatedUser, requested_org_id: Optional[str] = None) -> str:
    """
    Resolves the effective retailer organization identifier.
    - Company Admin: May inspect a specific retailer store org or defaults to 'ORG-RETAIL-METRO'.
    - Retailer: Strictly constrained to their own verified server-assigned org_id.
    - Any attempt by non-admins to specify a different organization is forbidden (HTTP 403).
    """
    if current_user.role == "admin":
        if requested_org_id and requested_org_id.strip():
            return requested_org_id.strip()
        if not current_user.org_id or current_user.org_id.startswith("ORG-FMCG"):
            return "ORG-RETAIL-METRO"
        return current_user.org_id

    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User identity has no associated retailer organization identifier.",
        )

    if requested_org_id and requested_org_id.strip() != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You are not authorized to access organization '{requested_org_id}'.",
        )

    return current_user.org_id


@router.get(
    "/dashboard",
    response_model=RetailerDashboardResponse,
    summary="Get retailer operational dashboard and KPI summary",
)
def get_retailer_dashboard(
    retailer_org_id: Optional[str] = Query(None, description="Retailer organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "retailer"])),
):
    """
    Returns store inventory summary, pending replenishment requests,
    approved requests awaiting fulfilment, in-transit consignments,
    and low-stock indicators.
    Strictly isolated to user's authorized retailer organization.
    """
    org_id = get_retailer_org_id(current_user, retailer_org_id)

    # 1. Retailer-Owned Inventory
    inv_records = (
        db.query(InventorySnapshot, Product, Location, Organization)
        .outerjoin(Product, InventorySnapshot.sku_id == Product.sku_id)
        .outerjoin(Location, InventorySnapshot.location_id == Location.location_id)
        .outerjoin(Organization, InventorySnapshot.owner_org_id == Organization.org_id)
        .filter(InventorySnapshot.owner_org_id == org_id)
        .all()
    )

    total_on_hand = sum(inv.on_hand for inv, _, _, _ in inv_records)
    total_available = sum(inv.dispatchable_stock for inv, _, _, _ in inv_records)
    distinct_skus = len(set(inv.sku_id for inv, _, _, _ in inv_records))

    # Low-stock SKU threshold (< 25 units available on shelf)
    low_stock_count = sum(1 for inv, _, _, _ in inv_records if inv.dispatchable_stock < 25)

    # 2. Replenishment Requests submitted by Retailer
    req_query = (
        db.query(Shipment)
        .filter(
            Shipment.owner_org_id == org_id,
            Shipment.planning_run_id.like("RET-REQ%"),
        )
        .order_by(desc(Shipment.created_at))
    )
    all_requests = req_query.all()
    pending_requests = [r for r in all_requests if r.approval_status == "pending"]
    approved_awaiting = [
        r for r in all_requests
        if r.approval_status == "approved" and r.status in ("approved", "ready_for_dispatch", "allocated")
    ]

    # 3. Shipments in Transit to / belonging to Retailer
    retail_loc_ids = [
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
                Shipment.destination_location_id.in_(retail_loc_ids) if retail_loc_ids else False,
            )
        )
        .order_by(desc(Shipment.created_at))
    )
    all_shipments = shipment_query.all()
    in_transit_count = sum(1 for s in all_shipments if s.status == "in_transit")

    return RetailerDashboardResponse(
        retailer_org_id=org_id,
        total_store_skus=distinct_skus,
        total_on_hand_units=round(total_on_hand, 2),
        total_available_units=round(total_available, 2),
        pending_requests_count=len(pending_requests),
        approved_awaiting_fulfilment_count=len(approved_awaiting),
        in_transit_shipments_count=in_transit_count,
        low_stock_skus_count=low_stock_count,
        recent_shipments=[map_shipment_response(s) for s in all_shipments[:10]],
        recent_requests=[map_shipment_response(r) for r in all_requests[:10]],
    )


@router.get(
    "/inventory",
    response_model=List[InventoryRecordResponse],
    summary="List retailer store inventory and shelf availability",
)
def get_retailer_inventory(
    sku_id: Optional[str] = None,
    location_id: Optional[str] = None,
    retailer_org_id: Optional[str] = Query(None, description="Retailer organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "retailer"])),
):
    """
    Returns inventory snapshots belonging to the caller's retailer organization.
    Conceals other retailers' stock and confidential manufacturer/distributor stocks.
    """
    org_id = get_retailer_org_id(current_user, retailer_org_id)

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
    summary="List replenishment requests submitted by the retailer",
)
def get_retailer_requests(
    retailer_org_id: Optional[str] = Query(None, description="Retailer organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "retailer"])),
):
    """
    Returns all store replenishment requests submitted by the retailer.
    """
    org_id = get_retailer_org_id(current_user, retailer_org_id)
    requests = (
        db.query(Shipment)
        .filter(
            Shipment.owner_org_id == org_id,
            Shipment.planning_run_id.like("RET-REQ%"),
        )
        .order_by(desc(Shipment.created_at))
        .all()
    )
    return [map_shipment_response(r) for r in requests]


@router.post(
    "/requests",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a store replenishment request",
)
def submit_retailer_request(
    payload: RetailerRequestCreatePayload,
    retailer_org_id: Optional[str] = Query(None, description="Retailer organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "retailer"])),
):
    """
    Submits a store replenishment request for the retailer.
    - Validates strictly positive quantity (> 0).
    - Persists request in 'proposed' state with approval_status 'pending'.
    - Logs audit StockMovement(movement_type='retailer_request').
    - DOES NOT directly alter physical stock, commit warehouse allocations, or dispatch goods.
    """
    org_id = get_retailer_org_id(current_user, retailer_org_id)

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

    # Resolve destination location: find retailer's own store/facility
    dest_loc = (
        db.query(Location)
        .filter(or_(Location.owner_org_id == org_id, Location.operator_org_id == org_id))
        .first()
    )
    dest_loc_id = dest_loc.location_id if dest_loc else "LOC-RETAIL-DEFAULT"
    src_loc_id = payload.preferred_source_location_id or "LOC-DIST-WEST"

    req_id = f"REQ-RET-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    planning_id = f"RET-REQ-{uuid.uuid4().hex[:6].upper()}"

    notes_str = f"RETAILER_REQUEST: {payload.reason or 'Store replenishment'}. Notes: {payload.notes or 'None'}"
    if payload.required_by_date:
        notes_str += f" [Required by: {payload.required_by_date}]"

    shipment = Shipment(
        shipment_id=req_id,
        sku_id=payload.sku_id.strip(),
        quantity=float(payload.quantity),
        source_location_id=src_loc_id,
        destination_location_id=dest_loc_id,
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
        source_location_id=src_loc_id,
        destination_location_id=dest_loc_id,
        quantity=float(payload.quantity),
        movement_type="retailer_request",
        status="proposed",
        timestamp=datetime.now(timezone.utc),
        notes=notes_str,
    )
    db.add(mov)

    # Add shipment event with explicit from_status='none'
    evt = ShipmentEvent(
        event_id=f"EVT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
        shipment_id=req_id,
        from_status="none",
        to_status="proposed",
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        notes="Retailer store replenishment request submitted",
    )
    db.add(evt)

    db.commit()
    db.refresh(shipment)
    return map_shipment_response(shipment)


@router.get(
    "/shipments",
    response_model=List[ShipmentResponse],
    summary="List shipments authorized for the retailer",
)
def get_retailer_shipments(
    status_filter: Optional[str] = Query(None, description="Optional shipment status filter"),
    retailer_org_id: Optional[str] = Query(None, description="Retailer organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "retailer"])),
):
    """
    Returns only shipments destined to or belonging to the retailer.
    """
    org_id = get_retailer_org_id(current_user, retailer_org_id)

    retail_loc_ids = [
        l.location_id
        for l in db.query(Location)
        .filter(or_(Location.owner_org_id == org_id, Location.operator_org_id == org_id))
        .all()
    ]

    query = db.query(Shipment).filter(
        or_(
            Shipment.owner_org_id == org_id,
            Shipment.destination_location_id.in_(retail_loc_ids) if retail_loc_ids else False,
        )
    ).order_by(desc(Shipment.created_at))

    if status_filter:
        query = query.filter(Shipment.status == status_filter.strip().lower())

    shipments = query.all()
    return [map_shipment_response(s) for s in shipments]


@router.post(
    "/shipments/{shipment_id}/confirm-receipt",
    response_model=ShipmentResponse,
    summary="Confirm received store shipment quantity and report discrepancies",
)
def confirm_retailer_receipt(
    shipment_id: str,
    payload: RetailerDeliveryConfirmPayload,
    retailer_org_id: Optional[str] = Query(None, description="Retailer organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "retailer"])),
):
    """
    Confirms physical receipt of goods at the retail store.
    - Validates caller belongs to recipient retailer organization.
    - Captures actual received quantity and condition status (intact, shortage, damaged, excess).
    - Prevents duplicate receipt confirmation.
    - Credits physical inventory snapshot at retailer store.
    - Logs auditable StockMovement and ShipmentEvent with user attribution.
    - Transitions shipment status to 'delivered'.
    """
    org_id = get_retailer_org_id(current_user, retailer_org_id)

    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id.strip()).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID '{shipment_id}' not found.",
        )

    # Check recipient authorization
    retail_loc_ids = [
        l.location_id
        for l in db.query(Location)
        .filter(or_(Location.owner_org_id == org_id, Location.operator_org_id == org_id))
        .all()
    ]
    is_dest = shipment.destination_location_id in retail_loc_ids
    is_owner = shipment.owner_org_id == org_id

    if current_user.role != "admin" and not (is_dest or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You are not authorized to confirm receipt for deliveries destined to another store.",
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
                f"with status '{shipment.status}'. Shipment must be 'in_transit' before store delivery confirmation."
            ),
        )

    if payload.received_quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Received quantity cannot be negative.",
        )

    now = datetime.now(timezone.utc)

    # Credit stock to store facility owned by retailer
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
            snapshot_id=f"SNAP-RET-REC-{now.strftime('%Y%m%d')}",
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
    discrepancy_str = f"Store delivery confirmed: {payload.received_quantity}/{shipment.quantity} units. Condition: {payload.condition_status}."
    if payload.discrepancy_units and payload.discrepancy_units > 0:
        discrepancy_str += f" Discrepancy: {payload.discrepancy_units} units."
    if payload.notes:
        discrepancy_str += f" Notes: {payload.notes}"

    if payload.condition_status != "intact" or (payload.discrepancy_units and payload.discrepancy_units > 0):
        shipment.exception_notes = discrepancy_str

    # Create immutable audit movement
    mov = StockMovement(
        movement_id=f"MOV-RREC-{uuid.uuid4().hex[:8].upper()}",
        shipment_id=shipment.shipment_id,
        sku_id=shipment.sku_id,
        source_location_id=shipment.source_location_id,
        destination_location_id=shipment.destination_location_id,
        quantity=float(payload.received_quantity),
        movement_type="retailer_receipt",
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
    summary="Cancel a pending store replenishment request",
)
def cancel_retailer_request(
    shipment_id: str,
    payload: RetailerRequestCancelPayload,
    retailer_org_id: Optional[str] = Query(None, description="Retailer organization ID (admin only)"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "retailer"])),
):
    """
    Cancels a pending store replenishment request.
    Only permitted when approval_status is 'pending' and shipment is 'proposed'.
    """
    org_id = get_retailer_org_id(current_user, retailer_org_id)

    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id.strip()).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store replenishment request '{shipment_id}' not found.",
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
    cancel_reason = payload.reason or "Cancelled by store manager."

    shipment.status = "cancelled"
    shipment.approval_status = "rejected"
    shipment.approval_notes = f"CANCELLED: {cancel_reason}"

    # Audit movement
    mov = StockMovement(
        movement_id=f"MOV-RCAN-{uuid.uuid4().hex[:8].upper()}",
        shipment_id=shipment.shipment_id,
        sku_id=shipment.sku_id,
        source_location_id=shipment.source_location_id,
        destination_location_id=shipment.destination_location_id,
        quantity=shipment.quantity,
        movement_type="retailer_cancellation",
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
        notes=f"Retailer store replenishment request cancelled. Reason: {cancel_reason}",
    )
    db.add(evt)

    db.commit()
    db.refresh(shipment)
    return map_shipment_response(shipment)

