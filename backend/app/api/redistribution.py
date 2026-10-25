from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.redistribution import (
    RedistributionSummaryResponse,
    CreateRedistributionProposalRequest,
)
from app.schemas.network import ShipmentResponse
from app.services.redistribution_service import (
    generate_redistribution_recommendations,
    create_redistribution_shipment_proposal,
)
from app.api.shipments import map_shipment_response
from app.core.security import AuthenticatedUser, require_roles

router = APIRouter(prefix="/redistribution", tags=["Authorized Redistribution & Expiry Prevention"])


@router.get(
    "/recommendations",
    response_model=RedistributionSummaryResponse,
    summary="Generate authorized redistribution recommendations for near-expiry and surplus stock",
)
def get_redistribution_recommendations(
    sku_id: Optional[str] = Query(None, description="Optional SKU filter"),
    source_location_id: Optional[str] = Query(None, description="Optional source facility filter"),
    max_expiry_days: int = Query(60, ge=1, le=180, description="Maximum days until expiry to consider at risk"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """
    Evaluates surplus finished goods and expiring batches at source facilities,
    pairing them with eligible destinations having unmet demand and sufficient remaining shelf life.
    Strictly isolated to user's authorized organization inventory.
    """
    result = generate_redistribution_recommendations(
        db=db,
        current_user=current_user,
        sku_id=sku_id,
        source_location_id=source_location_id,
        max_expiry_days=max_expiry_days,
    )
    return RedistributionSummaryResponse(**result)


@router.post(
    "/propose",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an authorized redistribution recommendation as a formal shipment proposal",
)
def submit_redistribution_proposal(
    payload: CreateRedistributionProposalRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """
    Converts a redistribution recommendation into a formal shipment proposal with status 'proposed'.
    Integrates directly with the existing approval, reservation, dispatch, and delivery governance lifecycle.
    Does NOT alter physical stock or auto-dispatch.
    """
    shipment = create_redistribution_shipment_proposal(
        db=db,
        current_user=current_user,
        payload=payload,
    )
    return map_shipment_response(shipment)
