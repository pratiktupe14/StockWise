from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models.entities import Shipment, StockMovement, ShipmentEvent
from app.schemas.network import (
    ShipmentProposalRequest,
    ShipmentResponse,
    ShipmentApprovalRequest,
    ShipmentStatusUpdateRequest,
    StockMovementResponse,
)
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
from app.services.network_service import (
    propose_shipment,
    approve_shipment,
    update_shipment_status,
)
from app.services import logistics_service
from app.core.security import AuthenticatedUser, require_roles
from app.services.idempotency_service import check_idempotency, record_idempotency
from app.core.config import settings
from fastapi import Header
from typing import Any

router = APIRouter(prefix="/shipments", tags=["Shipments & Logistics Execution"])


def check_shipment_tenant_access(shipment: Shipment, current_user: AuthenticatedUser, allow_carrier: bool = True) -> None:
    if current_user.role == "admin":
        return
    if not current_user.org_id:
        return
    if shipment.owner_org_id and shipment.owner_org_id != current_user.org_id:
        if allow_carrier and shipment.carrier_agency_id == current_user.org_id:
            return
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment.shipment_id}' not found."
        )


def resolve_actor_id(payload: Any, current_user: AuthenticatedUser) -> str:
    provided = getattr(payload, "authorized_user_id", None)
    if provided and (settings.ALLOW_DEMO_AUTH or current_user.role == "admin"):
        return provided
    return current_user.user_id


def map_shipment_response(s: Shipment) -> ShipmentResponse:
    return ShipmentResponse(
        shipment_id=s.shipment_id,
        sku_id=s.sku_id,
        product_name=s.product.name if s.product else s.sku_id,
        quantity=s.quantity,
        source_location_id=s.source_location_id,
        source_location_name=s.source_location.name if s.source_location else s.source_location_id,
        destination_location_id=s.destination_location_id,
        destination_location_name=s.destination_location.name if s.destination_location else s.destination_location_id,
        owner_org_id=s.owner_org_id,
        owner_org_name=s.owner_org.name if s.owner_org else None,
        carrier_agency_id=s.carrier_agency_id,
        carrier_agency_name=s.carrier_agency.name if s.carrier_agency else None,
        route_id=s.route_id,
        lead_time_days=s.route.lead_time_days if s.route else None,
        estimated_transport_cost=s.estimated_transport_cost,
        actual_transport_cost=s.actual_transport_cost,
        currency="INR",
        status=s.status,
        planning_run_id=s.planning_run_id,
        approval_status=s.approval_status,
        approved_by=s.approved_by,
        approval_notes=s.approval_notes,
        carrier_contact=s.carrier_contact,
        consignment_number=s.consignment_number,
        vehicle_number=s.vehicle_number,
        driver_contact=s.driver_contact,
        planned_pickup_date=s.planned_pickup_date,
        actual_pickup_date=s.actual_pickup_date,
        actual_delivery_date=s.actual_delivery_date,
        logistics_status=s.logistics_status,
        logistics_notes=s.logistics_notes,
        exception_reason=s.exception_reason,
        exception_notes=s.exception_notes,
        pod_reference=s.pod_reference,
        dispatch_checklist=s.dispatch_checklist,
        events_count=len(s.events) if s.events else 0,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("", response_model=List[ShipmentResponse], summary="List shipments")
def list_shipments(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    approval_status: Optional[str] = Query(None, description="Filter by approval status"),
    logistics_status: Optional[str] = Query(None, description="Filter by carrier assignment status"),
    sku_id: Optional[str] = Query(None, description="Filter by SKU ID"),
    source_location_id: Optional[str] = Query(None, description="Filter by source location"),
    destination_location_id: Optional[str] = Query(None, description="Filter by destination location"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    query = db.query(Shipment)
    if current_user.role != "admin" and current_user.org_id:
        query = query.filter(
            (Shipment.owner_org_id == current_user.org_id) |
            (Shipment.carrier_agency_id == current_user.org_id)
        )
    if status_filter:
        query = query.filter(Shipment.status == status_filter.lower().strip())
    if approval_status:
        query = query.filter(Shipment.approval_status == approval_status.lower().strip())
    if logistics_status:
        query = query.filter(Shipment.logistics_status == logistics_status.lower().strip())
    if sku_id:
        query = query.filter(Shipment.sku_id == sku_id.strip())
    if source_location_id:
        query = query.filter(Shipment.source_location_id == source_location_id.strip())
    if destination_location_id:
        query = query.filter(Shipment.destination_location_id == destination_location_id.strip())

    shipments = query.order_by(desc(Shipment.created_at)).limit(limit).all()
    return [map_shipment_response(s) for s in shipments]


@router.get("/movements", response_model=List[StockMovementResponse], summary="List stock movements audit log")
def list_stock_movements(
    shipment_id: Optional[str] = Query(None, description="Filter by shipment ID"),
    sku_id: Optional[str] = Query(None, description="Filter by SKU ID"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    query = db.query(StockMovement)
    if current_user.role != "admin" and current_user.org_id:
        query = query.join(Shipment, StockMovement.shipment_id == Shipment.shipment_id).filter(
            (Shipment.owner_org_id == current_user.org_id) |
            (Shipment.carrier_agency_id == current_user.org_id)
        )
    if shipment_id:
        query = query.filter(StockMovement.shipment_id == shipment_id.strip())
    if sku_id:
        query = query.filter(StockMovement.sku_id == sku_id.strip())

    movements = query.order_by(desc(StockMovement.timestamp)).limit(limit).all()
    results = []
    for m in movements:
        results.append(
            StockMovementResponse(
                movement_id=m.movement_id,
                shipment_id=m.shipment_id,
                sku_id=m.sku_id,
                product_name=m.product.name if m.product else m.sku_id,
                source_location_id=m.source_location_id,
                source_location_name=m.source.name if m.source else m.source_location_id,
                destination_location_id=m.destination_location_id,
                destination_location_name=m.destination.name if m.destination else m.destination_location_id,
                quantity=m.quantity,
                movement_type=m.movement_type,
                status=m.status,
                timestamp=m.timestamp,
                notes=m.notes,
            )
        )
    return results


@router.get("/{shipment_id}", response_model=ShipmentResponse, summary="Get shipment details")
def get_shipment(
    shipment_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found."
        )
    check_shipment_tenant_access(shipment, current_user, allow_carrier=True)
    return map_shipment_response(shipment)


@router.post("", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED, summary="Propose a new shipment")
@router.post("/propose", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED, summary="Propose a new shipment")
def propose_new_shipment(
    payload: ShipmentProposalRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    if current_user.role != "admin" and current_user.org_id:
        if payload.owner_org_id and payload.owner_org_id != current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: cannot propose shipment for organization '{payload.owner_org_id}'"
            )
        if not payload.owner_org_id:
            payload.owner_org_id = current_user.org_id
    shipment = propose_shipment(db, payload)
    return map_shipment_response(shipment)


@router.post("/{shipment_id}/approve", response_model=ShipmentResponse, summary="Approve or reject shipment")
def review_shipment_approval(
    shipment_id: str,
    payload: ShipmentApprovalRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found."
        )
    check_shipment_tenant_access(shipment, current_user, allow_carrier=False)

    endpoint_path = f"/api/shipments/{shipment_id}/approve"
    if idempotency_key:
        cached = check_idempotency(db, idempotency_key, endpoint_path, payload.model_dump())
        if cached:
            return ShipmentResponse(**cached[1])

    # Securely enforce authorized_user_id from verified token or authorized admin delegate
    payload.authorized_user_id = resolve_actor_id(payload, current_user)
    shipment = approve_shipment(db, shipment_id, payload)
    response = map_shipment_response(shipment)

    if idempotency_key:
        record_idempotency(
            db=db,
            key=idempotency_key,
            user_id=current_user.user_id,
            endpoint=endpoint_path,
            request_payload=payload.model_dump(),
            status_code=200,
            response_data=response.model_dump(mode="json"),
        )
    return response


@router.post("/{shipment_id}/status", response_model=ShipmentResponse, summary="Update shipment operational status")
def update_shipment_operational_status(
    shipment_id: str,
    payload: ShipmentStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "logistics"])),
):
    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found."
        )
    check_shipment_tenant_access(shipment, current_user, allow_carrier=True)
    shipment = update_shipment_status(db, shipment_id, payload)
    return map_shipment_response(shipment)


# =========================================================================
# Phase 4 Dedicated Execution & Governance Endpoints
# =========================================================================

@router.post("/{shipment_id}/stage", response_model=ShipmentResponse, summary="Stage shipment and reserve batches (alias for prepare)")
@router.post("/{shipment_id}/prepare", response_model=ShipmentResponse, summary="Stage shipment and record dispatch checklist")
def prepare_shipment_dispatch(
    shipment_id: str,
    payload: ShipmentDispatchPrepareRequest = ShipmentDispatchPrepareRequest(),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "logistics"])),
):
    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found."
        )
    check_shipment_tenant_access(shipment, current_user, allow_carrier=True)

    endpoint_path = f"/api/shipments/{shipment_id}/prepare"
    if idempotency_key:
        cached = check_idempotency(db, idempotency_key, endpoint_path, payload.model_dump())
        if cached:
            return ShipmentResponse(**cached[1])

    payload.authorized_user_id = resolve_actor_id(payload, current_user)
    shipment = logistics_service.prepare_dispatch(db, shipment_id, payload)
    response = map_shipment_response(shipment)

    if idempotency_key:
        record_idempotency(
            db=db,
            key=idempotency_key,
            user_id=current_user.user_id,
            endpoint=endpoint_path,
            request_payload=payload.model_dump(),
            status_code=200,
            response_data=response.model_dump(mode="json"),
        )
    return response


@router.post("/{shipment_id}/dispatch", response_model=ShipmentResponse, summary="Confirm physical dispatch into transit")
def confirm_shipment_dispatch(
    shipment_id: str,
    payload: ShipmentDispatchConfirmRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "logistics"])),
):
    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found."
        )
    check_shipment_tenant_access(shipment, current_user, allow_carrier=True)

    endpoint_path = f"/api/shipments/{shipment_id}/dispatch"
    if idempotency_key:
        cached = check_idempotency(db, idempotency_key, endpoint_path, payload.model_dump())
        if cached:
            return ShipmentResponse(**cached[1])

    payload.authorized_user_id = resolve_actor_id(payload, current_user)
    shipment = logistics_service.confirm_dispatch(db, shipment_id, payload)
    response = map_shipment_response(shipment)

    if idempotency_key:
        record_idempotency(
            db=db,
            key=idempotency_key,
            user_id=current_user.user_id,
            endpoint=endpoint_path,
            request_payload=payload.model_dump(),
            status_code=200,
            response_data=response.model_dump(mode="json"),
        )
    return response


@router.post("/{shipment_id}/deliver", response_model=ShipmentResponse, summary="Confirm physical delivery at destination")
def confirm_shipment_delivery(
    shipment_id: str,
    payload: ShipmentDeliveryConfirmRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "logistics"])),
):
    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found."
        )
    check_shipment_tenant_access(shipment, current_user, allow_carrier=True)

    endpoint_path = f"/api/shipments/{shipment_id}/deliver"
    if idempotency_key:
        cached = check_idempotency(db, idempotency_key, endpoint_path, payload.model_dump())
        if cached:
            return ShipmentResponse(**cached[1])

    payload.authorized_user_id = resolve_actor_id(payload, current_user)
    shipment = logistics_service.confirm_delivery(db, shipment_id, payload)
    response = map_shipment_response(shipment)

    if idempotency_key:
        record_idempotency(
            db=db,
            key=idempotency_key,
            user_id=current_user.user_id,
            endpoint=endpoint_path,
            request_payload=payload.model_dump(),
            status_code=200,
            response_data=response.model_dump(mode="json"),
        )
    return response


@router.post("/{shipment_id}/assign-carrier", response_model=ShipmentResponse, summary="Assign carrier logistics provider")
def assign_carrier_agency(
    shipment_id: str,
    payload: ShipmentCarrierAssignRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "logistics"])),
):
    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found."
        )
    check_shipment_tenant_access(shipment, current_user, allow_carrier=False)
    payload.authorized_user_id = resolve_actor_id(payload, current_user)
    shipment = logistics_service.assign_carrier(db, shipment_id, payload)
    return map_shipment_response(shipment)


@router.post("/{shipment_id}/carrier-decision", response_model=ShipmentResponse, summary="Logistics agency acceptance or rejection")
def review_carrier_decision(
    shipment_id: str,
    payload: ShipmentCarrierDecisionRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "logistics"])),
):
    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found."
        )
    check_shipment_tenant_access(shipment, current_user, allow_carrier=True)
    payload.authorized_user_id = resolve_actor_id(payload, current_user)
    shipment = logistics_service.decide_carrier_assignment(db, shipment_id, payload)
    return map_shipment_response(shipment)


@router.post("/{shipment_id}/exception", response_model=ShipmentResponse, summary="Record operational exception or delay")
def log_operational_exception(
    shipment_id: str,
    payload: ShipmentExceptionRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "logistics"])),
):
    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found."
        )
    check_shipment_tenant_access(shipment, current_user, allow_carrier=True)
    payload.authorized_user_id = resolve_actor_id(payload, current_user)
    shipment = logistics_service.record_exception(db, shipment_id, payload)
    return map_shipment_response(shipment)


@router.post("/{shipment_id}/cancel", response_model=ShipmentResponse, summary="Cancel shipment and reverse reservations")
def cancel_shipment_execution(
    shipment_id: str,
    authorized_user_id: Optional[str] = Query(None),
    actor_role: Optional[str] = Query("operations_manager"),
    notes: Optional[str] = Query(None),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found."
        )
    check_shipment_tenant_access(shipment, current_user, allow_carrier=False)

    user_id = authorized_user_id if (authorized_user_id and (settings.ALLOW_DEMO_AUTH or current_user.role == "admin")) else current_user.user_id
    endpoint_path = f"/api/shipments/{shipment_id}/cancel"
    payload_dict = {"shipment_id": shipment_id, "user_id": user_id, "notes": notes}

    if idempotency_key:
        cached = check_idempotency(db, idempotency_key, endpoint_path, payload_dict)
        if cached:
            return ShipmentResponse(**cached[1])

    shipment = logistics_service.cancel_shipment(db, shipment_id, user_id, actor_role or current_user.role, notes)
    response = map_shipment_response(shipment)

    if idempotency_key:
        record_idempotency(
            db=db,
            key=idempotency_key,
            user_id=user_id,
            endpoint=endpoint_path,
            request_payload=payload_dict,
            status_code=200,
            response_data=response.model_dump(mode="json"),
        )
    return response


@router.get("/{shipment_id}/events", response_model=List[ShipmentEventResponse], summary="Retrieve shipment audit event trail")
def list_shipment_event_history(
    shipment_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found."
        )
    check_shipment_tenant_access(shipment, current_user, allow_carrier=True)
    events = logistics_service.get_shipment_events(db, shipment_id)
    return [
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


@router.get("/{shipment_id}/traceability", response_model=ShipmentTraceabilityResponse, summary="Retrieve full plan-to-execution traceability")
def get_traceability(
    shipment_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found."
        )
    check_shipment_tenant_access(shipment, current_user, allow_carrier=True)
    return logistics_service.get_shipment_traceability(db, shipment_id)
