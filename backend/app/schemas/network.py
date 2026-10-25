from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# --- Organization Schemas ---
class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    org_type: str = Field(..., description="fmcg_company, cnf_agency, logistics_provider, distributor, retailer")
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    is_active: bool = True


class OrganizationCreate(OrganizationBase):
    org_id: str = Field(..., min_length=2, max_length=64)


class OrganizationResponse(OrganizationBase):
    model_config = ConfigDict(from_attributes=True)

    org_id: str
    created_at: datetime
    updated_at: datetime


# --- Location Schemas ---
class LocationExtendedCreate(BaseModel):
    location_id: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=2, max_length=255)
    location_type: str = Field(..., description="manufacturing_plant, company_warehouse, central_warehouse, regional_warehouse, cnf_facility, 3pl_facility, distributor_warehouse, retail_destination")
    region: str = Field(..., min_length=2, max_length=128)
    city: Optional[str] = None
    address: Optional[str] = None
    owner_org_id: Optional[str] = None
    operator_org_id: Optional[str] = None
    storage_capacity_units: Optional[float] = Field(None, ge=0)
    dispatch_capacity_daily: Optional[float] = Field(None, ge=0)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: bool = True


class LocationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    location_type: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    owner_org_id: Optional[str] = None
    operator_org_id: Optional[str] = None
    storage_capacity_units: Optional[float] = Field(None, ge=0)
    dispatch_capacity_daily: Optional[float] = Field(None, ge=0)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = None



class LocationExtendedResponse(BaseModel):
    location_id: str
    name: str
    location_type: str
    region: str
    city: Optional[str] = None
    address: Optional[str] = None
    owner_org_id: Optional[str] = None
    owner_org_name: Optional[str] = None
    operator_org_id: Optional[str] = None
    operator_org_name: Optional[str] = None
    storage_capacity_units: Optional[float] = None
    dispatch_capacity_daily: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Route Schemas ---
class RouteCreate(BaseModel):
    from_location_id: str
    to_location_id: str
    carrier_agency_id: Optional[str] = None
    lead_time_days: float = Field(..., gt=0, description="Lead time in days (>0)")
    cost_rate: float = Field(..., ge=0, description="Transport cost rate (>=0)")
    capacity_units: Optional[float] = Field(None, gt=0)
    sku_eligibility: Optional[str] = "all"
    pricing_basis: str = Field("per_unit", description="per_unit, per_case, per_trip")
    min_shipment_qty: Optional[float] = Field(None, ge=0)
    max_shipment_qty: Optional[float] = Field(None, ge=0)
    is_active: bool = True
    status_notes: Optional[str] = None


class RouteExtendedResponse(BaseModel):
    id: int
    from_location_id: str
    from_location_name: Optional[str] = None
    from_location_type: Optional[str] = None
    to_location_id: str
    to_location_name: Optional[str] = None
    to_location_type: Optional[str] = None
    carrier_agency_id: Optional[str] = None
    carrier_agency_name: Optional[str] = None
    lead_time_days: float
    cost_rate: float
    capacity_units: Optional[float] = None
    sku_eligibility: Optional[str] = "all"
    pricing_basis: str
    min_shipment_qty: Optional[float] = None
    max_shipment_qty: Optional[float] = None
    is_active: bool
    status_notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Eligibility Analysis Schemas ---
class RouteEligibilityCheck(BaseModel):
    route_id: int
    from_location_id: str
    from_location_name: str
    to_location_id: str
    to_location_name: str
    carrier_agency_name: Optional[str] = None
    is_eligible: bool
    rejection_reasons: List[str]
    lead_time_days: float
    cost_rate: float


class UnserviceableLocationInfo(BaseModel):
    location_id: str
    name: str
    location_type: str
    region: str
    reason: str


class NetworkEligibilityResponse(BaseModel):
    total_locations: int
    active_locations: int
    total_routes: int
    active_routes: int
    eligible_corridors: List[RouteEligibilityCheck]
    unserviceable_destinations: List[UnserviceableLocationInfo]
    summary_message: str


# --- Shipment & Movement Schemas ---
class ShipmentProposalRequest(BaseModel):
    sku_id: str
    source_location_id: str
    destination_location_id: str
    quantity: float = Field(..., gt=0, description="Quantity to move (>0)")
    owner_org_id: Optional[str] = None
    carrier_agency_id: Optional[str] = None
    planning_run_id: Optional[str] = None
    estimated_dispatch_date: Optional[datetime] = None
    notes: Optional[str] = None


class ShipmentResponse(BaseModel):
    shipment_id: str
    sku_id: str
    product_name: Optional[str] = None
    quantity: float
    source_location_id: str
    source_location_name: Optional[str] = None
    destination_location_id: str
    destination_location_name: Optional[str] = None
    owner_org_id: Optional[str] = None
    owner_org_name: Optional[str] = None
    carrier_agency_id: Optional[str] = None
    carrier_agency_name: Optional[str] = None
    route_id: Optional[int] = None
    lead_time_days: Optional[float] = None
    estimated_transport_cost: float
    actual_transport_cost: Optional[float] = None
    currency: str = "INR"
    status: str
    planning_run_id: Optional[str] = None
    approval_status: str
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None
    carrier_contact: Optional[str] = None
    consignment_number: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_contact: Optional[str] = None
    planned_pickup_date: Optional[datetime] = None
    actual_pickup_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    logistics_status: str = "unassigned"
    logistics_notes: Optional[str] = None
    exception_reason: Optional[str] = None
    exception_notes: Optional[str] = None
    pod_reference: Optional[str] = None
    dispatch_checklist: Optional[str] = None
    events_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShipmentApprovalRequest(BaseModel):
    approved: bool
    authorized_user_id: str = Field(..., min_length=2)
    notes: Optional[str] = None


class ShipmentStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="ready_for_dispatch, in_transit, delivered, cancelled")
    notes: Optional[str] = None


class StockMovementResponse(BaseModel):
    movement_id: str
    shipment_id: Optional[str] = None
    sku_id: str
    product_name: Optional[str] = None
    source_location_id: str
    source_location_name: Optional[str] = None
    destination_location_id: str
    destination_location_name: Optional[str] = None
    quantity: float
    movement_type: str
    status: str
    timestamp: datetime
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
