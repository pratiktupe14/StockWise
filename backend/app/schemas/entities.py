from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku_id: str
    name: str
    category: Optional[str] = "General"
    unit: str = "cases"
    case_pack: int = 1
    shelf_life_days: Optional[int] = None
    created_at: datetime


class ProductCreate(BaseModel):
    sku_id: str = Field(..., min_length=2, max_length=64, description="Unique SKU code")
    name: str = Field(..., min_length=2, max_length=255, description="Product display name")
    category: Optional[str] = Field("General", max_length=128, description="Product category")
    unit: str = Field("cases", max_length=32, description="Unit of measurement")
    case_pack: int = Field(1, ge=1, description="Units per case pack")
    shelf_life_days: Optional[int] = Field(None, ge=1, description="Shelf life in days")


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    category: Optional[str] = Field(None, max_length=128)
    unit: Optional[str] = Field(None, max_length=32)
    case_pack: Optional[int] = Field(None, ge=1)
    shelf_life_days: Optional[int] = Field(None, ge=1)


class CategorySummaryItem(BaseModel):
    category: str
    product_count: int


class AdminUserItem(BaseModel):
    user_id: str
    email: str
    role: str
    org_id: Optional[str] = None
    org_name: Optional[str] = None
    is_active: bool = True



class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    location_id: str
    name: str
    location_type: str
    region: str
    address: Optional[str] = None
    created_at: datetime


class InventoryRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: str
    sku_id: str
    product_name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = "cases"
    location_id: str
    location_name: Optional[str] = None
    region: Optional[str] = None
    on_hand: float
    reserved: float
    blocked: float
    confirmed_incoming: float
    dispatchable_stock: float = Field(..., description="max(0, on_hand - reserved - blocked)")
    as_of_date: date
    owner_org_id: Optional[str] = None
    owner_org_name: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    created_at: datetime


class SalesHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku_id: str
    product_name: Optional[str] = None
    destination_id: str
    destination_name: Optional[str] = None
    sales_date: date
    quantity: float
    created_at: datetime


class RouteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_location_id: str
    from_location_name: Optional[str] = None
    to_location_id: str
    to_location_name: Optional[str] = None
    lead_time_days: float
    cost_rate: float
    capacity_units: Optional[float] = None
    sku_eligibility: Optional[str] = "all"
    carrier_agency_id: Optional[str] = None
    pricing_basis: Optional[str] = "per_unit"
    created_at: datetime


class BatchExpiryRiskItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    snapshot_id: str
    sku_id: str
    product_name: Optional[str] = None
    location_id: str
    location_name: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    days_remaining: Optional[int] = None
    risk_category: str
    on_hand: float
    reserved: float
    blocked: float
    dispatchable_quantity: float
    is_dispatchable: bool
    owner_org_id: Optional[str] = None


class ExpiryRiskSummaryResponse(BaseModel):
    total_batches: int
    expired_batches: int
    expired_units: float
    critical_batches: int
    critical_units: float
    high_risk_batches: int
    high_risk_units: float
    medium_risk_batches: int
    medium_risk_units: float
    healthy_batches: int
    healthy_units: float
    unknown_expiry_batches: int
    unknown_expiry_units: float
    total_dispatchable_units: float
    items: list[BatchExpiryRiskItem]


class FEFOAllocationRequest(BaseModel):
    sku_id: str
    demand_quantity: float = Field(..., gt=0, description="Required dispatch units")
    source_location_id: Optional[str] = Field(None, description="Optional facility constraint")
    destination_location_id: Optional[str] = Field(None, description="Optional destination reference")
    min_remaining_shelf_life_days: int = Field(0, ge=0, description="Minimum days shelf life required at receipt")


class BatchAllocationItem(BaseModel):
    snapshot_id: str
    batch_number: Optional[str] = None
    location_id: str
    expiry_date: Optional[date] = None
    days_remaining: Optional[int] = None
    allocated_quantity: float
    available_before_allocation: float
    remaining_after_allocation: float


class FEFOAllocationResponse(BaseModel):
    sku_id: str
    demand_quantity: float
    total_allocated: float
    unmet_demand: float
    is_fully_allocated: bool
    min_remaining_shelf_life_days: int
    allocations: list[BatchAllocationItem]

