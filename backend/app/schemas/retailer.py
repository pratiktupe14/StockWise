from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.entities import InventoryRecordResponse
from app.schemas.network import ShipmentResponse


class RetailerDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    retailer_org_id: str
    total_store_skus: int
    total_on_hand_units: float
    total_available_units: float
    pending_requests_count: int
    approved_awaiting_fulfilment_count: int
    in_transit_shipments_count: int
    low_stock_skus_count: int
    recent_shipments: List[ShipmentResponse]
    recent_requests: List[ShipmentResponse]


class RetailerRequestCreatePayload(BaseModel):
    sku_id: str = Field(..., min_length=2, description="Target product SKU")
    quantity: float = Field(..., gt=0, description="Requested replenishment units (>0)")
    preferred_source_location_id: Optional[str] = Field(None, description="Preferred regional distributor or DC")
    required_by_date: Optional[str] = Field(None, description="Requested required-by delivery date")
    reason: Optional[str] = Field("Store replenishment", description="Business reason for replenishment")
    notes: Optional[str] = Field(None, description="Delivery or shelf instructions")


class RetailerDeliveryConfirmPayload(BaseModel):
    received_quantity: float = Field(..., ge=0, description="Quantity actually received into retailer store")
    condition_status: str = Field("intact", description="Condition: intact, shortage, damaged, excess")
    discrepancy_units: Optional[float] = Field(0.0, ge=0, description="Shortage or excess quantity in cases")
    notes: Optional[str] = Field(None, description="Store receiving remarks, damaged goods details, or discrepancy note")


class RetailerRequestCancelPayload(BaseModel):
    reason: Optional[str] = Field(None, description="Reason for cancelling store replenishment request")

