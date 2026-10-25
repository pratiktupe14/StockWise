from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.entities import InventoryRecordResponse
from app.schemas.network import ShipmentResponse


class DistributorDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    distributor_org_id: str
    total_owned_skus: int
    total_on_hand_units: float
    total_dispatchable_units: float
    pending_requests_count: int
    in_transit_shipments_count: int
    near_expiry_batches_count: int
    recent_shipments: List[ShipmentResponse]
    recent_requests: List[ShipmentResponse]


class DistributorRequestCreatePayload(BaseModel):
    sku_id: str = Field(..., min_length=2, description="Target SKU")
    quantity: float = Field(..., gt=0, description="Requested units (>0)")
    destination_location_id: Optional[str] = Field(None, description="Distributor receiving facility")
    source_location_id: Optional[str] = Field(None, description="Preferred company source DC")
    reason: Optional[str] = Field("Replenishment request", description="Commercial requirement reason")
    notes: Optional[str] = Field(None, description="Additional context or timing constraints")


class DistributorDeliveryConfirmPayload(BaseModel):
    received_quantity: float = Field(..., ge=0, description="Quantity actually received into distributor facility")
    condition_status: str = Field("intact", description="Condition: intact, shortage, damaged, excess")
    discrepancy_units: Optional[float] = Field(0.0, ge=0, description="Shortage or excess quantity in cases")
    notes: Optional[str] = Field(None, description="Receiving remarks, damaged batch details, or discrepancy explanation")


class DistributorRequestCancelPayload(BaseModel):
    reason: Optional[str] = Field(None, description="Reason for cancelling replenishment request")

