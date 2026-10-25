"""Pydantic schemas for Phase 4: Logistics Agency Coordination & Shipment Execution."""
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class ShipmentEventResponse(BaseModel):
    event_id: str
    shipment_id: str
    from_status: str
    to_status: str
    actor_id: str
    actor_role: Optional[str] = None
    notes: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShipmentDispatchPrepareRequest(BaseModel):
    authorized_user_id: Optional[str] = Field("LOG-SUPERVISOR-01", description="ID of warehouse supervisor/operator")
    actor_role: Optional[str] = Field("warehouse_supervisor", description="Role of the actor")
    checklist_items: List[str] = Field(
        default_factory=lambda: [
            "packaging_inspected",
            "quantity_reconciled",
            "dock_assigned",
            "batch_verified"
        ],
        description="Completed warehouse readiness checklist items"
    )
    notes: Optional[str] = Field(None, description="Readiness notes, dock number, bay allocation")


class ShipmentCarrierAssignRequest(BaseModel):
    carrier_agency_id: str = Field(..., min_length=2, description="Logistics agency organization ID")
    carrier_contact: Optional[str] = Field(None, description="Responsible carrier coordinator contact")
    planned_pickup_date: Optional[datetime] = None
    estimated_arrival_date: Optional[datetime] = None
    authorized_user_id: str = Field(..., min_length=2)
    actor_role: Optional[str] = Field("logistics_coordinator", description="Role of the actor")
    notes: Optional[str] = None


class ShipmentCarrierDecisionRequest(BaseModel):
    accepted: bool = Field(..., description="True if logistics agency accepts, False if rejected")
    authorized_user_id: str = Field(..., min_length=2, description="Logistics coordinator / agency contact ID")
    actor_role: Optional[str] = Field("logistics_agency", description="Role of the actor")
    consignment_number: Optional[str] = Field(None, description="Waybill or consignment tracking reference")
    vehicle_number: Optional[str] = Field(None, description="Assigned transport vehicle plate number")
    driver_contact: Optional[str] = Field(None, description="Driver name and mobile contact")
    notes: Optional[str] = Field(None, description="Acceptance confirmation or rejection reason")


class ShipmentDispatchConfirmRequest(BaseModel):
    authorized_user_id: Optional[str] = Field("LOG-DISPATCH-01", description="Warehouse dispatch manager recording physical pickup")
    actor_role: Optional[str] = Field("warehouse_manager", description="Role of the actor")
    actual_pickup_date: Optional[datetime] = None
    consignment_number: Optional[str] = Field(None, description="Consignment or Bilty number")
    vehicle_number: Optional[str] = Field(None, description="Truck or vehicle registration number")
    driver_contact: Optional[str] = Field(None, description="Driver name and phone")
    notes: Optional[str] = Field(None, description="Dispatch gate pass / gate-out remarks")


class ShipmentDeliveryConfirmRequest(BaseModel):
    authorized_user_id: str = Field(..., min_length=2, description="Receiving location officer")
    actor_role: Optional[str] = Field("receiving_officer", description="Role of the actor")
    actual_delivery_date: Optional[datetime] = None
    actual_transport_cost: Optional[float] = Field(None, ge=0, description="Final freight cost in reporting currency (INR)")
    pod_reference: Optional[str] = Field(None, description="Proof of Delivery acknowledgment / signed docket ID")
    notes: Optional[str] = Field(None, description="Receiving condition notes, seal verification, dock receipt")


class ShipmentExceptionRequest(BaseModel):
    authorized_user_id: str = Field(..., min_length=2)
    actor_role: Optional[str] = Field("logistics_coordinator", description="Role of the actor")
    exception_reason: str = Field(..., min_length=2, description="Delay reason, weather disruption, breakdown, or failed delivery")
    notes: Optional[str] = Field(None, description="Detailed incident narrative and corrective action")


class ShipmentTraceabilityResponse(BaseModel):
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
    carrier_contact: Optional[str] = None
    route_id: Optional[int] = None
    lead_time_days: Optional[float] = None
    currency: str = "INR"
    estimated_transport_cost: float
    actual_transport_cost: Optional[float] = None
    status: str
    approval_status: str
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None
    logistics_status: str
    consignment_number: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_contact: Optional[str] = None
    planned_pickup_date: Optional[datetime] = None
    actual_pickup_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    exception_reason: Optional[str] = None
    exception_notes: Optional[str] = None
    pod_reference: Optional[str] = None
    dispatch_checklist: Optional[str] = None
    planning_run_id: Optional[str] = None
    decision_rationale: Optional[str] = None
    planning_run_metadata: Optional[Dict[str, Any]] = None
    decision_receipt: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    events: List[ShipmentEventResponse] = Field(default_factory=list)
    movements: List[Dict[str, Any]] = Field(default_factory=list)
