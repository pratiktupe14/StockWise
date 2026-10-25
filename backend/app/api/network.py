from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.models.entities import Organization, Location, Route, Product
from app.schemas.entities import AdminUserItem
from app.schemas.network import (
    OrganizationCreate,
    OrganizationResponse,
    LocationExtendedCreate,
    LocationExtendedResponse,
    LocationUpdate,
    RouteCreate,
    RouteExtendedResponse,
    NetworkEligibilityResponse,
)
from app.services.network_service import analyze_network_eligibility, check_route_eligibility
from app.core.security import (
    AuthenticatedUser,
    require_roles,
    RequireAuthenticated,
    SERVER_VERIFIED_USER_MAPPINGS,
    DEMO_PERSONAS,
)


router = APIRouter(prefix="", tags=["Distribution Network"])


# --- Organizations ---
@router.get("/organizations", response_model=List[OrganizationResponse], summary="List all organizations")
def list_organizations(
    org_type: Optional[str] = Query(None, description="Filter by type: fmcg_company, cnf_agency, logistics_provider, distributor, retailer"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    query = db.query(Organization)
    if org_type:
        query = query.filter(Organization.org_type == org_type.lower().strip())
    if is_active is not None:
        query = query.filter(Organization.is_active == is_active)
    return query.order_by(Organization.name.asc()).all()


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED, summary="Register organization")
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin"])),
):
    existing = db.query(Organization).filter(Organization.org_id == payload.org_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization with ID '{payload.org_id}' already exists."
        )

    valid_types = {"fmcg_company", "cnf_agency", "logistics_provider", "distributor", "independent_distributor", "retailer"}
    if payload.org_type.lower() not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid org_type '{payload.org_type}'. Allowed: {sorted(list(valid_types))}"
        )

    org = Organization(
        org_id=payload.org_id.strip(),
        name=payload.name.strip(),
        org_type=payload.org_type.lower().strip(),
        contact_email=payload.contact_email.strip() if payload.contact_email else None,
        contact_phone=payload.contact_phone.strip() if payload.contact_phone else None,
        is_active=payload.is_active,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


# --- Network Locations ---
@router.get("/network/locations", response_model=List[LocationExtendedResponse], summary="List network facilities & locations")
def list_network_locations(
    location_type: Optional[str] = Query(None, description="Filter by location type"),
    region: Optional[str] = Query(None, description="Filter by region"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    query = db.query(Location)
    if location_type:
        query = query.filter(Location.location_type == location_type.lower().strip())
    if region:
        query = query.filter(Location.region.ilike(f"%{region.strip()}%"))
    if is_active is not None:
        query = query.filter(Location.is_active == is_active)

    locations = query.order_by(Location.name.asc()).all()
    results = []
    for loc in locations:
        results.append(
            LocationExtendedResponse(
                location_id=loc.location_id,
                name=loc.name,
                location_type=loc.location_type,
                region=loc.region,
                city=loc.city,
                address=loc.address,
                owner_org_id=loc.owner_org_id,
                owner_org_name=loc.owner_org.name if loc.owner_org else None,
                operator_org_id=loc.operator_org_id,
                operator_org_name=loc.operator_org.name if loc.operator_org else None,
                storage_capacity_units=loc.storage_capacity_units,
                dispatch_capacity_daily=loc.dispatch_capacity_daily,
                latitude=loc.latitude,
                longitude=loc.longitude,
                is_active=loc.is_active,
                created_at=loc.created_at,
                updated_at=loc.updated_at,
            )
        )
    return results


@router.post("/network/locations", response_model=LocationExtendedResponse, status_code=status.HTTP_201_CREATED, summary="Create network location")
def create_network_location(
    payload: LocationExtendedCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin"])),
):
    existing = db.query(Location).filter(Location.location_id == payload.location_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Location with ID '{payload.location_id}' already exists."
        )

    # Validate organization references if provided
    if payload.owner_org_id:
        owner = db.query(Organization).filter(Organization.org_id == payload.owner_org_id).first()
        if not owner:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Owner organization '{payload.owner_org_id}' does not exist."
            )
    if payload.operator_org_id:
        operator = db.query(Organization).filter(Organization.org_id == payload.operator_org_id).first()
        if not operator:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Operator organization '{payload.operator_org_id}' does not exist."
            )

    loc = Location(
        location_id=payload.location_id.strip(),
        name=payload.name.strip(),
        location_type=payload.location_type.strip(),
        region=payload.region.strip(),
        city=payload.city.strip() if payload.city else None,
        address=payload.address.strip() if payload.address else None,
        owner_org_id=payload.owner_org_id,
        operator_org_id=payload.operator_org_id,
        storage_capacity_units=payload.storage_capacity_units,
        dispatch_capacity_daily=payload.dispatch_capacity_daily,
        latitude=payload.latitude,
        longitude=payload.longitude,
        is_active=payload.is_active,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)

    return LocationExtendedResponse(
        location_id=loc.location_id,
        name=loc.name,
        location_type=loc.location_type,
        region=loc.region,
        city=loc.city,
        address=loc.address,
        owner_org_id=loc.owner_org_id,
        owner_org_name=loc.owner_org.name if loc.owner_org else None,
        operator_org_id=loc.operator_org_id,
        operator_org_name=loc.operator_org.name if loc.operator_org else None,
        storage_capacity_units=loc.storage_capacity_units,
        dispatch_capacity_daily=loc.dispatch_capacity_daily,
        latitude=loc.latitude,
        longitude=loc.longitude,
        is_active=loc.is_active,
        created_at=loc.created_at,
        updated_at=loc.updated_at,
    )


@router.put("/network/locations/{location_id}", response_model=LocationExtendedResponse, summary="Update facility and warehouse details")
def update_network_location(
    location_id: str,
    payload: LocationUpdate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin"])),
):
    """
    Updates facility specifications, capacities, ownership, and operational status.
    Restricted to Company Admin.
    """
    loc = db.query(Location).filter(Location.location_id == location_id.strip()).first()
    if not loc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID '{location_id}' not found.",
        )

    if payload.owner_org_id is not None:
        if payload.owner_org_id != "":
            owner = db.query(Organization).filter(Organization.org_id == payload.owner_org_id).first()
            if not owner:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Owner organization '{payload.owner_org_id}' does not exist.",
                )
            loc.owner_org_id = payload.owner_org_id
        else:
            loc.owner_org_id = None

    if payload.operator_org_id is not None:
        if payload.operator_org_id != "":
            operator = db.query(Organization).filter(Organization.org_id == payload.operator_org_id).first()
            if not operator:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Operator organization '{payload.operator_org_id}' does not exist.",
                )
            loc.operator_org_id = payload.operator_org_id
        else:
            loc.operator_org_id = None

    if payload.name is not None:
        loc.name = payload.name.strip()
    if payload.location_type is not None:
        loc.location_type = payload.location_type.strip()
    if payload.region is not None:
        loc.region = payload.region.strip()
    if payload.city is not None:
        loc.city = payload.city.strip()
    if payload.address is not None:
        loc.address = payload.address.strip()
    if payload.storage_capacity_units is not None:
        loc.storage_capacity_units = payload.storage_capacity_units
    if payload.dispatch_capacity_daily is not None:
        loc.dispatch_capacity_daily = payload.dispatch_capacity_daily
    if payload.latitude is not None:
        loc.latitude = payload.latitude
    if payload.longitude is not None:
        loc.longitude = payload.longitude
    if payload.is_active is not None:
        loc.is_active = payload.is_active

    db.commit()
    db.refresh(loc)

    return LocationExtendedResponse(
        location_id=loc.location_id,
        name=loc.name,
        location_type=loc.location_type,
        region=loc.region,
        city=loc.city,
        address=loc.address,
        owner_org_id=loc.owner_org_id,
        owner_org_name=loc.owner_org.name if loc.owner_org else None,
        operator_org_id=loc.operator_org_id,
        operator_org_name=loc.operator_org.name if loc.operator_org else None,
        storage_capacity_units=loc.storage_capacity_units,
        dispatch_capacity_daily=loc.dispatch_capacity_daily,
        latitude=loc.latitude,
        longitude=loc.longitude,
        is_active=loc.is_active,
        created_at=loc.created_at,
        updated_at=loc.updated_at,
    )


@router.get("/admin/users", response_model=List[AdminUserItem], summary="List authorized users and role assignments")
def list_admin_users(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin"])),
):
    """
    Returns trusted user accounts, roles, tenant organization assignments,
    and operational access status. Restricted to Company Admin.
    """
    users = []
    orgs = {o.org_id: o.name for o in db.query(Organization).all()}

    for email, meta in SERVER_VERIFIED_USER_MAPPINGS.items():
        role = meta["role"]
        org_id = meta["org_id"]
        persona = DEMO_PERSONAS.get(role)
        uid = persona.user_id if persona else f"USER-{role.upper()}"
        users.append(
            AdminUserItem(
                user_id=uid,
                email=email,
                role=role,
                org_id=org_id,
                org_name=orgs.get(org_id, org_id),
                is_active=True,
            )
        )
    return users


# --- Permitted Routes ---

@router.get("/network/routes", response_model=List[RouteExtendedResponse], summary="List permitted distribution routes")
def list_network_routes(
    is_active: Optional[bool] = Query(None, description="Filter active routes"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    query = db.query(Route)
    if is_active is not None:
        query = query.filter(Route.is_active == is_active)

    routes = query.all()
    results = []
    for r in routes:
        results.append(
            RouteExtendedResponse(
                id=r.id,
                from_location_id=r.from_location_id,
                from_location_name=r.from_location.name if r.from_location else r.from_location_id,
                from_location_type=r.from_location.location_type if r.from_location else None,
                to_location_id=r.to_location_id,
                to_location_name=r.to_location.name if r.to_location else r.to_location_id,
                to_location_type=r.to_location.location_type if r.to_location else None,
                carrier_agency_id=r.carrier_agency_id,
                carrier_agency_name=r.carrier_agency.name if r.carrier_agency else None,
                lead_time_days=r.lead_time_days,
                cost_rate=r.cost_rate,
                capacity_units=r.capacity_units,
                sku_eligibility=r.sku_eligibility or "all",
                pricing_basis=r.pricing_basis or "per_unit",
                min_shipment_qty=r.min_shipment_qty,
                max_shipment_qty=r.max_shipment_qty,
                is_active=r.is_active,
                status_notes=r.status_notes,
                created_at=r.created_at,
            )
        )
    return results


@router.post("/network/routes", response_model=RouteExtendedResponse, status_code=status.HTTP_201_CREATED, summary="Create or configure permitted route")
def create_network_route(
    payload: RouteCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin"])),
):
    # Rule: cannot be self-referencing
    if payload.from_location_id == payload.to_location_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source and destination cannot be identical ('{payload.from_location_id}')."
        )

    # Validate source and destination exist
    src = db.query(Location).filter(Location.location_id == payload.from_location_id).first()
    if not src:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source location '{payload.from_location_id}' not found."
        )

    dst = db.query(Location).filter(Location.location_id == payload.to_location_id).first()
    if not dst:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Destination location '{payload.to_location_id}' not found."
        )

    # Validate carrier agency if provided
    if payload.carrier_agency_id:
        carrier = db.query(Organization).filter(Organization.org_id == payload.carrier_agency_id).first()
        if not carrier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Carrier agency '{payload.carrier_agency_id}' not found."
            )

    # Check duplicate route
    existing = db.query(Route).filter(
        Route.from_location_id == payload.from_location_id,
        Route.to_location_id == payload.to_location_id,
    ).first()

    if existing:
        # Update existing route configuration
        existing.carrier_agency_id = payload.carrier_agency_id
        existing.lead_time_days = payload.lead_time_days
        existing.cost_rate = payload.cost_rate
        existing.capacity_units = payload.capacity_units
        existing.sku_eligibility = payload.sku_eligibility or "all"
        existing.pricing_basis = payload.pricing_basis
        existing.min_shipment_qty = payload.min_shipment_qty
        existing.max_shipment_qty = payload.max_shipment_qty
        existing.is_active = payload.is_active
        existing.status_notes = payload.status_notes
        db.commit()
        db.refresh(existing)
        r = existing
    else:
        r = Route(
            from_location_id=payload.from_location_id,
            to_location_id=payload.to_location_id,
            carrier_agency_id=payload.carrier_agency_id,
            lead_time_days=payload.lead_time_days,
            cost_rate=payload.cost_rate,
            capacity_units=payload.capacity_units,
            sku_eligibility=payload.sku_eligibility or "all",
            pricing_basis=payload.pricing_basis,
            min_shipment_qty=payload.min_shipment_qty,
            max_shipment_qty=payload.max_shipment_qty,
            is_active=payload.is_active,
            status_notes=payload.status_notes,
        )
        db.add(r)
        db.commit()
        db.refresh(r)

    return RouteExtendedResponse(
        id=r.id,
        from_location_id=r.from_location_id,
        from_location_name=r.from_location.name if r.from_location else r.from_location_id,
        from_location_type=r.from_location.location_type if r.from_location else None,
        to_location_id=r.to_location_id,
        to_location_name=r.to_location.name if r.to_location else r.to_location_id,
        to_location_type=r.to_location.location_type if r.to_location else None,
        carrier_agency_id=r.carrier_agency_id,
        carrier_agency_name=r.carrier_agency.name if r.carrier_agency else None,
        lead_time_days=r.lead_time_days,
        cost_rate=r.cost_rate,
        capacity_units=r.capacity_units,
        sku_eligibility=r.sku_eligibility or "all",
        pricing_basis=r.pricing_basis or "per_unit",
        min_shipment_qty=r.min_shipment_qty,
        max_shipment_qty=r.max_shipment_qty,
        is_active=r.is_active,
        status_notes=r.status_notes,
        created_at=r.created_at,
    )


# --- Network Eligibility Analysis ---
@router.get("/network/eligibility", response_model=NetworkEligibilityResponse, summary="Analyze distribution network eligibility")
def get_network_eligibility(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    """
    Evaluates configured corridors, flags unserviceable destinations,
    and identifies reasons why routes are eligible or rejected.
    """
    return analyze_network_eligibility(db)
