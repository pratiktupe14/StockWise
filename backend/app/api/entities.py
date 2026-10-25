from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models.entities import (
    Product,
    Location,
    InventorySnapshot,
    SalesHistory,
    Route,
    Organization,
    Shipment,
    StockMovement,
)
from app.schemas.entities import (
    ProductResponse,
    ProductCreate,
    ProductUpdate,
    CategorySummaryItem,
    LocationResponse,
    InventoryRecordResponse,
    SalesHistoryResponse,
    RouteResponse,
    ExpiryRiskSummaryResponse,
    FEFOAllocationRequest,
    FEFOAllocationResponse,
)
from app.services.expiry_service import summarize_expiry_risk, allocate_fefo_batches
from app.core.security import AuthenticatedUser, RequireAuthenticated, require_roles

router = APIRouter(tags=["Operational Entities"])


@router.get("/products", response_model=List[ProductResponse], summary="List validated products")
def list_products(
    category: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    """Returns validated product and SKU master records."""
    query = db.query(Product).order_by(Product.sku_id.asc())
    if category:
        query = query.filter(Product.category == category)
    return query.limit(limit).all()


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, summary="Create a new product SKU")
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin"])),
):
    """
    Creates a new product SKU. Restricted to Company Admin.
    Validates unique SKU code and required attributes.
    """
    existing = db.query(Product).filter(Product.sku_id == payload.sku_id.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product with SKU '{payload.sku_id.strip()}' already exists.",
        )

    product = Product(
        sku_id=payload.sku_id.strip(),
        name=payload.name.strip(),
        category=payload.category.strip() if payload.category else "General",
        unit=payload.unit.strip() if payload.unit else "cases",
        case_pack=payload.case_pack,
        shelf_life_days=payload.shelf_life_days,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/products/{sku_id}", response_model=ProductResponse, summary="Update product SKU details")
def update_product(
    sku_id: str,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin"])),
):
    """
    Updates product specifications. Restricted to Company Admin.
    """
    product = db.query(Product).filter(Product.sku_id == sku_id.strip()).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with SKU '{sku_id}' not found.",
        )

    if payload.name is not None:
        product.name = payload.name.strip()
    if payload.category is not None:
        product.category = payload.category.strip()
    if payload.unit is not None:
        product.unit = payload.unit.strip()
    if payload.case_pack is not None:
        product.case_pack = payload.case_pack
    if payload.shelf_life_days is not None:
        product.shelf_life_days = payload.shelf_life_days

    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{sku_id}", summary="Deactivate or delete product SKU")
def delete_product(
    sku_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin"])),
):
    """
    Safely deletes a product SKU.
    Prevents deletion if historical transactions (inventory, shipments, or sales) exist
    to avoid silently corrupting historical records.
    """
    product = db.query(Product).filter(Product.sku_id == sku_id.strip()).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with SKU '{sku_id}' not found.",
        )

    # Check for historical references
    inv_count = db.query(InventorySnapshot).filter(InventorySnapshot.sku_id == sku_id.strip()).count()
    shipment_count = db.query(Shipment).filter(Shipment.sku_id == sku_id.strip()).count()
    sales_count = db.query(SalesHistory).filter(SalesHistory.sku_id == sku_id.strip()).count()
    movement_count = db.query(StockMovement).filter(StockMovement.sku_id == sku_id.strip()).count()

    total_refs = inv_count + shipment_count + sales_count + movement_count
    if total_refs > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"CANNOT_DELETE_ACTIVE_PRODUCT: Product '{sku_id}' has {total_refs} associated historical "
                f"transactions (Inventory: {inv_count}, Shipments: {shipment_count}, Sales: {sales_count}, Movements: {movement_count}) "
                "and cannot be deleted to preserve transactional audit integrity."
            ),
        )

    db.delete(product)
    db.commit()
    return {"message": f"Product '{sku_id}' deleted successfully.", "sku_id": sku_id, "deleted": True}


@router.get("/categories", response_model=List[CategorySummaryItem], summary="List product categories and SKU counts")
def list_categories(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    """Returns summary of product categories with total SKU count."""
    results = (
        db.query(Product.category, func.count(Product.sku_id).label("count"))
        .group_by(Product.category)
        .order_by(Product.category.asc())
        .all()
    )
    return [
        CategorySummaryItem(
            category=cat or "General",
            product_count=cnt,
        )
        for cat, cnt in results
    ]



@router.get("/locations", response_model=List[LocationResponse], summary="List validated locations")
def list_locations(
    location_type: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    """Returns validated warehouse, distribution center, and retail locations."""
    query = db.query(Location).order_by(Location.location_id.asc())
    if location_type:
        query = query.filter(Location.location_type == location_type.lower())
    if region:
        query = query.filter(Location.region == region)
    return query.limit(limit).all()


@router.get("/inventory", response_model=List[InventoryRecordResponse], summary="List inventory snapshots")
def list_inventory(
    snapshot_id: Optional[str] = None,
    location_id: Optional[str] = None,
    sku_id: Optional[str] = None,
    owner_org_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    """
    Returns inventory snapshots with mathematically computed dispatchable stock.
    Current dispatchable stock = max(0, on_hand - reserved - blocked).
    Strict tenant isolation: Non-admins can only query inventory owned by their trusted organization.
    """
    query = (
        db.query(InventorySnapshot, Product, Location, Organization)
        .outerjoin(Product, InventorySnapshot.sku_id == Product.sku_id)
        .outerjoin(Location, InventorySnapshot.location_id == Location.location_id)
        .outerjoin(Organization, InventorySnapshot.owner_org_id == Organization.org_id)
        .order_by(InventorySnapshot.location_id.asc(), InventorySnapshot.sku_id.asc())
    )

    # Tenant isolation enforcement: non-admin users can ONLY access stock of their assigned organization
    if current_user.role != "admin":
        if current_user.org_id:
            query = query.filter(InventorySnapshot.owner_org_id == current_user.org_id)
        else:
            return []
    elif owner_org_id:
        query = query.filter(InventorySnapshot.owner_org_id == owner_org_id.strip())

    if snapshot_id:
        query = query.filter(InventorySnapshot.snapshot_id == snapshot_id)
    if location_id:
        query = query.filter(InventorySnapshot.location_id == location_id)
    if sku_id:
        query = query.filter(InventorySnapshot.sku_id == sku_id)

    results = query.limit(limit).all()

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


@router.get("/inventory/expiry-risk", response_model=ExpiryRiskSummaryResponse, summary="Expiry risk analytics and batch health summary")
def get_inventory_expiry_risk(
    sku_id: Optional[str] = None,
    location_id: Optional[str] = None,
    owner_org_id: Optional[str] = None,
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    """
    Computes deterministic expiry risk analytics across inventory batches.
    Respects organization-level tenant isolation.
    """
    query = (
        db.query(InventorySnapshot)
        .outerjoin(Product, InventorySnapshot.sku_id == Product.sku_id)
        .outerjoin(Location, InventorySnapshot.location_id == Location.location_id)
        .order_by(InventorySnapshot.expiry_date.asc())
    )

    if current_user.role != "admin":
        if current_user.org_id:
            query = query.filter(InventorySnapshot.owner_org_id == current_user.org_id)
        else:
            return ExpiryRiskSummaryResponse(
                total_batches=0, expired_batches=0, expired_units=0.0,
                critical_batches=0, critical_units=0.0, high_risk_batches=0,
                high_risk_units=0.0, medium_risk_batches=0, medium_risk_units=0.0,
                healthy_batches=0, healthy_units=0.0, unknown_expiry_batches=0,
                unknown_expiry_units=0.0, total_dispatchable_units=0.0, items=[]
            )
    elif owner_org_id:
        query = query.filter(InventorySnapshot.owner_org_id == owner_org_id.strip())

    if sku_id:
        query = query.filter(InventorySnapshot.sku_id == sku_id.strip())
    if location_id:
        query = query.filter(InventorySnapshot.location_id == location_id.strip())

    snapshots = query.limit(limit).all()
    summary = summarize_expiry_risk(snapshots)
    return ExpiryRiskSummaryResponse(**summary)


@router.post("/inventory/fefo-allocate", response_model=FEFOAllocationResponse, summary="Deterministic FEFO allocation across eligible batches")
def allocate_inventory_fefo(
    payload: FEFOAllocationRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    """
    Deterministic First-Expired, First-Out (FEFO) batch allocator.
    Prioritizes eligible batches strictly by earliest valid expiry date.
    Excludes expired and blocked stock, and explicitly returns unmet demand.
    """
    query = db.query(InventorySnapshot).filter(InventorySnapshot.sku_id == payload.sku_id.strip())

    if current_user.role != "admin":
        if current_user.org_id:
            query = query.filter(InventorySnapshot.owner_org_id == current_user.org_id)
        else:
            return FEFOAllocationResponse(
                sku_id=payload.sku_id,
                demand_quantity=payload.demand_quantity,
                total_allocated=0.0,
                unmet_demand=payload.demand_quantity,
                is_fully_allocated=False,
                min_remaining_shelf_life_days=payload.min_remaining_shelf_life_days,
                allocations=[],
            )

    if payload.source_location_id:
        query = query.filter(InventorySnapshot.location_id == payload.source_location_id.strip())

    snapshots = query.all()
    res = allocate_fefo_batches(
        batches=snapshots,
        demand_quantity=payload.demand_quantity,
        min_remaining_shelf_life_days=payload.min_remaining_shelf_life_days,
    )
    return FEFOAllocationResponse(sku_id=payload.sku_id, **res)


@router.get("/sales", response_model=List[SalesHistoryResponse], summary="List sales history")
def list_sales_history(
    sku_id: Optional[str] = None,
    destination_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    """Returns validated historical consumption records."""
    query = (
        db.query(SalesHistory, Product, Location)
        .outerjoin(Product, SalesHistory.sku_id == Product.sku_id)
        .outerjoin(Location, SalesHistory.destination_id == Location.location_id)
        .order_by(SalesHistory.sales_date.desc())
    )

    if sku_id:
        query = query.filter(SalesHistory.sku_id == sku_id)
    if destination_id:
        query = query.filter(SalesHistory.destination_id == destination_id)

    results = query.limit(limit).all()
    records = []
    for sale, prod, dest in results:
        records.append(
            SalesHistoryResponse(
                id=sale.id,
                sku_id=sale.sku_id,
                product_name=prod.name if prod else None,
                destination_id=sale.destination_id,
                destination_name=dest.name if dest else None,
                sales_date=sale.sales_date,
                quantity=sale.quantity,
                created_at=sale.created_at,
            )
        )
    return records


@router.get("/routes", response_model=List[RouteResponse], summary="List permitted routes")
def list_routes(
    from_id: Optional[str] = None,
    to_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    """Returns permitted transport lanes and carrier cost rates."""
    loc_from = db.query(Location).subquery("loc_from")
    loc_to = db.query(Location).subquery("loc_to")

    query = (
        db.query(
            Route,
            loc_from.c.name.label("from_name"),
            loc_to.c.name.label("to_name"),
        )
        .outerjoin(loc_from, Route.from_location_id == loc_from.c.location_id)
        .outerjoin(loc_to, Route.to_location_id == loc_to.c.location_id)
        .order_by(Route.from_location_id.asc(), Route.to_location_id.asc())
    )

    if from_id:
        query = query.filter(Route.from_location_id == from_id)
    if to_id:
        query = query.filter(Route.to_location_id == to_id)

    results = query.limit(limit).all()
    records = []
    for r, f_name, t_name in results:
        records.append(
            RouteResponse(
                id=r.id,
                from_location_id=r.from_location_id,
                from_location_name=f_name,
                to_location_id=r.to_location_id,
                to_location_name=t_name,
                lead_time_days=r.lead_time_days,
                cost_rate=r.cost_rate,
                capacity_units=r.capacity_units,
                sku_eligibility=r.sku_eligibility,
                created_at=r.created_at,
            )
        )
    return records
