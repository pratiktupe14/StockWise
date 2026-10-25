from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ImportRowErrorSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    row_index: int = Field(..., description="1-based original file row number")
    field_name: Optional[str] = Field(None, description="Name of the rejected field")
    rejected_value: Optional[str] = Field(None, description="Value that failed validation")
    error_reason: str = Field(..., description="Human-readable explanation of why the row was rejected")
    error_code: str = Field(..., description="Machine-readable error code")


class ImportRunSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str = Field(..., description="Unique ID for this import execution")
    dataset_type: str = Field(..., description="products, locations, inventory, sales, routes")
    filename: str = Field(..., description="Original uploaded file name")
    file_format: str = Field(..., description="csv or xlsx")
    file_size_bytes: int = Field(..., description="Size of file in bytes")
    total_rows: int = Field(..., description="Total rows parsed")
    valid_rows: int = Field(..., description="Count of accepted valid rows")
    rejected_rows: int = Field(..., description="Count of rejected rows")
    inserted_rows: int = Field(0, description="Count of newly inserted records")
    updated_rows: int = Field(0, description="Count of updated existing records")
    skipped_rows: int = Field(0, description="Count of skipped unchanged/duplicate records")
    status: str = Field(..., description="'completed', 'partial', or 'failed'")
    snapshot_id: Optional[str] = Field(None, description="Associated snapshot identifier if applicable")
    created_at: datetime = Field(..., description="Timestamp of import execution")
    errors: List[ImportRowErrorSchema] = Field(default_factory=list, description="Row-level validation errors")


class ImportRunListResponse(BaseModel):
    total_runs: int
    runs: List[ImportRunSummaryResponse]
