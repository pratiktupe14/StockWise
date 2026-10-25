from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class RedistributionRecommendation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recommendation_id: str
    sku_id: str
    product_name: Optional[str] = None
    source_location_id: str
    source_location_name: Optional[str] = None
    destination_location_id: str
    destination_location_name: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    days_remaining: Optional[int] = None
    risk_category: str
    source_available_units: float
    destination_unmet_demand: float
    recommended_quantity: float
    lead_time_days: float
    expected_delivery_date: date
    shelf_life_days_at_arrival: int
    estimated_transport_cost: float
    priority_score: float
    rationale: str
    owner_org_id: str


class RedistributionRejectedCandidate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku_id: str
    source_location_id: str
    destination_location_id: str
    batch_number: Optional[str] = None
    rejection_reason: str


class RedistributionSummaryResponse(BaseModel):
    generated_at: datetime
    total_candidates_analyzed: int
    recommendations_count: int
    potential_units_saved: float
    total_estimated_transport_cost: float
    recommendations: List[RedistributionRecommendation]
    rejected_candidates: List[RedistributionRejectedCandidate]


class CreateRedistributionProposalRequest(BaseModel):
    sku_id: str = Field(..., min_length=2)
    source_location_id: str = Field(..., min_length=2)
    destination_location_id: str = Field(..., min_length=2)
    quantity: float = Field(..., gt=0)
    batch_number: Optional[str] = None
    notes: Optional[str] = None
