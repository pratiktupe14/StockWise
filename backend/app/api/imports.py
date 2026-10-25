import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException, status, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.entities import (
    Product,
    Location,
    InventorySnapshot,
    SalesHistory,
    Route,
    ImportRun,
    ImportRowError,
    Organization,
)
from app.schemas.imports import ImportRunSummaryResponse, ImportRunListResponse, ImportRowErrorSchema
from app.services.file_parser import parse_uploaded_file
from app.services.validators import (
    DATASET_TYPES,
    validate_products_dataset,
    validate_locations_dataset,
    validate_inventory_dataset,
    validate_sales_dataset,
    validate_routes_dataset,
    validate_organizations_dataset,
)
from app.services.templates import generate_template_csv, generate_template_excel
from app.core.security import AuthenticatedUser, require_roles, RequireAuthenticated

router = APIRouter(prefix="/imports", tags=["Imports & Validation"])


@router.get("/templates/{dataset_type}", summary="Download dataset template")
def download_template(
    dataset_type: str,
    format: str = Query("csv", description="File format: 'csv' or 'xlsx'"),
    current_user: AuthenticatedUser = RequireAuthenticated,
):
    """Provides downloadable CSV or Excel templates with sample data for each dataset type."""
    norm_type = dataset_type.lower().strip()
    if norm_type not in DATASET_TYPES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown dataset type '{dataset_type}'. Supported: {', '.join(DATASET_TYPES)}"
        )

    if format.lower() == "xlsx":
        content = generate_template_excel(norm_type)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=StockWise_template_{norm_type}.xlsx"}
        )
    else:
        content = generate_template_csv(norm_type)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=StockWise_template_{norm_type}.csv"}
        )


@router.post(
    "/{dataset_type}/preview",
    response_model=ImportRunSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview and validate dataset without committing",
)
async def preview_dataset(
    dataset_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """
    Validates CSV or Excel dataset without committing to master tables.
    Allows planners to review valid row counts and row-level rejection details beforehand.
    """
    norm_type = dataset_type.lower().strip()
    if norm_type not in DATASET_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported dataset type '{dataset_type}'. Supported types: {', '.join(DATASET_TYPES)}"
        )

    rows, file_format, file_size_bytes = await parse_uploaded_file(file)
    run_id = f"PREVIEW-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    filename = file.filename or "unknown"

    valid_records = []
    validation_errors = []

    if norm_type == "products":
        valid_records, validation_errors = validate_products_dataset(rows, db)
    elif norm_type == "organizations":
        valid_records, validation_errors = validate_organizations_dataset(rows, db)
    elif norm_type == "locations":
        valid_records, validation_errors = validate_locations_dataset(rows, db)
    elif norm_type == "inventory":
        valid_records, validation_errors = validate_inventory_dataset(rows, db)
    elif norm_type == "sales":
        valid_records, validation_errors = validate_sales_dataset(rows, db)
    elif norm_type == "routes":
        valid_records, validation_errors = validate_routes_dataset(rows, db)

    total_rows = len(rows)
    valid_count = len(valid_records)
    rejected_count = total_rows - valid_count

    if valid_count == total_rows and rejected_count == 0:
        run_status = "preview_valid"
    elif valid_count > 0 and rejected_count > 0:
        run_status = "preview_partial"
    else:
        run_status = "preview_failed"

    return ImportRunSummaryResponse(
        run_id=run_id,
        dataset_type=norm_type,
        filename=filename,
        file_format=file_format,
        file_size_bytes=file_size_bytes,
        total_rows=total_rows,
        valid_rows=valid_count,
        rejected_rows=rejected_count,
        status=run_status,
        snapshot_id=None,
        created_at=datetime.now(timezone.utc),
        errors=[
            ImportRowErrorSchema(
                row_index=e.row_index,
                field_name=e.field_name,
                rejected_value=e.rejected_value,
                error_reason=e.error_reason,
                error_code=e.error_code,
            )
            for e in validation_errors
        ],
    )


@router.post(
    "/{dataset_type}",
    response_model=ImportRunSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload and validate a dataset",
)
async def upload_dataset(
    dataset_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """
    Ingests and validates CSV or Excel dataset files.
    - Validates schema, headers, types, and values.
    - Separates valid records from rejected records.
    - Persists valid records into database.
    - Persists audit run and row-level error log.
    - Rejects invalid records without silently converting them.
    """
    norm_type = dataset_type.lower().strip()
    if norm_type not in DATASET_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported dataset type '{dataset_type}'. Supported types: {', '.join(DATASET_TYPES)}"
        )

    rows, file_format, file_size_bytes = await parse_uploaded_file(file)

    if norm_type == "organizations" and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only administrators can import organization master data."
        )

    run_id = f"IMP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    filename = file.filename or "unknown"
    snapshot_id = None
    inserted_rows = 0
    updated_rows = 0

    valid_records = []
    validation_errors = []

    # Run specific dataset validator
    if norm_type == "products":
        valid_records, validation_errors = validate_products_dataset(rows, db)
        for rec in valid_records:
            existing = db.query(Product).filter(Product.sku_id == rec["sku_id"]).first()
            if existing:
                existing.name = rec["name"]
                existing.category = rec["category"]
                existing.unit = rec["unit"]
                existing.case_pack = rec["case_pack"]
                existing.shelf_life_days = rec["shelf_life_days"]
                updated_rows += 1
            else:
                db.add(Product(**rec))
                inserted_rows += 1

    elif norm_type == "organizations":
        valid_records, validation_errors = validate_organizations_dataset(rows, db)
        for rec in valid_records:
            existing = db.query(Organization).filter(Organization.org_id == rec["org_id"]).first()
            if existing:
                existing.name = rec["name"]
                existing.org_type = rec["org_type"]
                existing.contact_email = rec.get("contact_email")
                existing.contact_phone = rec.get("contact_phone")
                existing.is_active = rec.get("is_active", True)
                updated_rows += 1
            else:
                db.add(Organization(**rec))
                inserted_rows += 1

    elif norm_type == "locations":
        valid_records, validation_errors = validate_locations_dataset(rows, db)
        for rec in valid_records:
            if not rec.get("owner_org_id"):
                rec["owner_org_id"] = current_user.org_id or "ORG-FMCG-CORP"
            if not rec.get("operator_org_id"):
                rec["operator_org_id"] = rec["owner_org_id"]

            if current_user.role != "admin" and rec.get("owner_org_id") and rec["owner_org_id"] != current_user.org_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: Cannot create location for external organization '{rec.get('owner_org_id')}'.",
                )
            existing = db.query(Location).filter(Location.location_id == rec["location_id"]).first()
            if existing:
                existing.name = rec["name"]
                existing.location_type = rec["location_type"]
                existing.region = rec["region"]
                existing.city = rec.get("city")
                existing.address = rec.get("address")
                existing.owner_org_id = rec.get("owner_org_id")
                existing.operator_org_id = rec.get("operator_org_id")
                existing.storage_capacity_units = rec.get("storage_capacity_units")
                existing.dispatch_capacity_daily = rec.get("dispatch_capacity_daily")
                existing.latitude = rec.get("latitude")
                existing.longitude = rec.get("longitude")
                existing.is_active = rec.get("is_active", True)
                updated_rows += 1
            else:
                db.add(Location(**rec))
                inserted_rows += 1

    elif norm_type == "inventory":
        valid_records, validation_errors = validate_inventory_dataset(rows, db)
        if valid_records:
            snapshot_id = valid_records[0].get("snapshot_id") or "SNAP-DEFAULT"
        for rec in valid_records:
            if not rec.get("owner_org_id"):
                rec["owner_org_id"] = current_user.org_id or "ORG-FMCG-CORP"

            # Enforce that non-admins can only import stock for their assigned org
            if current_user.role != "admin":
                if rec.get("owner_org_id") and rec["owner_org_id"] != current_user.org_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Forbidden: Cannot import stock for external organization '{rec.get('owner_org_id')}'.",
                    )

            existing = db.query(InventorySnapshot).filter(
                InventorySnapshot.snapshot_id == rec["snapshot_id"],
                InventorySnapshot.sku_id == rec["sku_id"],
                InventorySnapshot.location_id == rec["location_id"],
            ).first()
            if existing:
                existing.on_hand = rec["on_hand"]
                existing.reserved = rec["reserved"]
                existing.blocked = rec["blocked"]
                existing.confirmed_incoming = rec["confirmed_incoming"]
                existing.as_of_date = rec["as_of_date"]
                existing.owner_org_id = rec.get("owner_org_id")
                existing.batch_number = rec.get("batch_number")
                existing.expiry_date = rec.get("expiry_date")
                updated_rows += 1
            else:
                db.add(InventorySnapshot(**rec))
                inserted_rows += 1

    elif norm_type == "sales":
        valid_records, validation_errors = validate_sales_dataset(rows, db)
        for rec in valid_records:
            existing = db.query(SalesHistory).filter(
                SalesHistory.sku_id == rec["sku_id"],
                SalesHistory.destination_id == rec["destination_id"],
                SalesHistory.sales_date == rec["sales_date"],
            ).first()
            if existing:
                existing.quantity = rec["quantity"]
                updated_rows += 1
            else:
                db.add(SalesHistory(**rec))
                inserted_rows += 1

    elif norm_type == "routes":
        valid_records, validation_errors = validate_routes_dataset(rows, db)
        for rec in valid_records:
            if not rec.get("carrier_agency_id"):
                rec["carrier_agency_id"] = current_user.org_id or "ORG-LOGISTICS-3PL"

            existing = db.query(Route).filter(
                Route.from_location_id == rec["from_location_id"],
                Route.to_location_id == rec["to_location_id"],
            ).first()
            if existing:
                existing.carrier_agency_id = rec.get("carrier_agency_id")
                existing.lead_time_days = rec["lead_time_days"]
                existing.cost_rate = rec["cost_rate"]
                existing.capacity_units = rec.get("capacity_units")
                existing.sku_eligibility = rec.get("sku_eligibility", "all")
                existing.pricing_basis = rec.get("pricing_basis", "per_unit")
                existing.min_shipment_qty = rec.get("min_shipment_qty")
                existing.max_shipment_qty = rec.get("max_shipment_qty")
                existing.is_active = rec.get("is_active", True)
                existing.status_notes = rec.get("status_notes")
                updated_rows += 1
            else:
                db.add(Route(**rec))
                inserted_rows += 1

    # Determine status
    total_rows = len(rows)
    valid_count = len(valid_records)
    rejected_count = total_rows - valid_count

    if valid_count == total_rows and rejected_count == 0:
        run_status = "completed"
    elif valid_count > 0 and rejected_count > 0:
        run_status = "partial"
    else:
        run_status = "failed"

    # Create import run record with authenticated tenant context
    import_run = ImportRun(
        run_id=run_id,
        dataset_type=norm_type,
        filename=filename,
        file_format=file_format,
        file_size_bytes=file_size_bytes,
        total_rows=total_rows,
        valid_rows=valid_count,
        rejected_rows=rejected_count,
        status=run_status,
        snapshot_id=snapshot_id,
        org_id=current_user.org_id,
        created_by_user_id=current_user.user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(import_run)

    # Persist row errors
    db_errors = []
    for err in validation_errors:
        db_err = ImportRowError(
            run_id=run_id,
            row_index=err.row_index,
            field_name=err.field_name,
            rejected_value=err.rejected_value,
            error_reason=err.error_reason,
            error_code=err.error_code,
            created_at=datetime.now(timezone.utc),
        )
        db.add(db_err)
        db_errors.append(db_err)

    try:
        db.commit()
        db.refresh(import_run)
    except Exception:
        db.rollback()
        raise

    return ImportRunSummaryResponse(
        run_id=import_run.run_id,
        dataset_type=import_run.dataset_type,
        filename=import_run.filename,
        file_format=import_run.file_format,
        file_size_bytes=import_run.file_size_bytes,
        total_rows=import_run.total_rows,
        valid_rows=import_run.valid_rows,
        rejected_rows=import_run.rejected_rows,
        inserted_rows=inserted_rows,
        updated_rows=updated_rows,
        skipped_rows=0,
        status=import_run.status,
        snapshot_id=import_run.snapshot_id,
        created_at=import_run.created_at,
        errors=[ImportRowErrorSchema.model_validate(e) for e in db_errors],
    )


@router.get("", response_model=ImportRunListResponse, summary="List import history")
def list_import_runs(
    dataset_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Retrieves chronological import runs and their completion statuses scoped to tenant."""
    query = db.query(ImportRun).order_by(ImportRun.created_at.desc())
    if current_user.role != "admin":
        if current_user.org_id:
            query = query.filter(ImportRun.org_id == current_user.org_id)
        else:
            return ImportRunListResponse(total_runs=0, runs=[])

    if dataset_type:
        query = query.filter(ImportRun.dataset_type == dataset_type.lower().strip())

    runs = query.limit(limit).all()
    total = query.count()

    response_runs = []
    for r in runs:
        # Load associated errors
        errs = db.query(ImportRowError).filter(ImportRowError.run_id == r.run_id).all()
        response_runs.append(
            ImportRunSummaryResponse(
                run_id=r.run_id,
                dataset_type=r.dataset_type,
                filename=r.filename,
                file_format=r.file_format,
                file_size_bytes=r.file_size_bytes,
                total_rows=r.total_rows,
                valid_rows=r.valid_rows,
                rejected_rows=r.rejected_rows,
                status=r.status,
                snapshot_id=r.snapshot_id,
                created_at=r.created_at,
                errors=[ImportRowErrorSchema.model_validate(e) for e in errs],
            )
        )

    return ImportRunListResponse(total_runs=total, runs=response_runs)


# --- Phase 5: Dataset Readiness & Traceable Public Dataset Sources ---

@router.get("/readiness", summary="Get comprehensive dataset sources and readiness status")
def get_dataset_readiness(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """
    Returns the comprehensive readiness status of all public datasets and operational data in StockWise.
    Shows source, coverage, category, import status, record counts, license, downstream features,
    and missing required operational datasets.
    """
    from app.services.dataset_service import get_dataset_registry_and_readiness
    return get_dataset_registry_and_readiness(db)


@router.post("/benchmarks/ingest", summary="Ingest public benchmark dataset reproducibly")
def ingest_benchmark_dataset(
    dataset_id: str = Query("all", description="Dataset identifier: 'all', 'osm_india_network', 'uci_online_retail'"),
    force_reload: bool = Query(False, description="Whether to overwrite existing records"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """
    Reproducibly executes the dataset ingestion pipeline for permitted public datasets:
    - OpenStreetMap verified Indian FMCG logistics nodes & OSRM road routes
    - UCI Online Retail II real products, filtered sales time series & FEFO inventory balances
    All benchmark records are isolated under BENCHMARK-COMPANY and SNAP-BENCHMARK-PUBLIC.
    """
    from app.services.dataset_service import (
        ingest_osm_india_network,
        ingest_uci_online_retail_benchmark,
    )

    results = {}
    norm_id = dataset_id.lower().strip()

    if norm_id in ("all", "osm_india_network"):
        results["osm_india_network"] = ingest_osm_india_network(db, force_reload=force_reload)

    if norm_id in ("all", "uci_online_retail"):
        results["uci_online_retail"] = ingest_uci_online_retail_benchmark(db, force_reload=force_reload)

    if not results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown benchmark dataset '{dataset_id}'. Supported: 'all', 'osm_india_network', 'uci_online_retail'",
        )

    total_records = 0
    for k, v in results.items():
        if isinstance(v, dict):
            total_records += (
                v.get("records_ingested")
                or v.get("routes_ingested")
                or v.get("sales_ingested")
                or v.get("locations_ingested")
                or v.get("total_ingested")
                or 0
            )

    return {
        "status": "completed",
        "authorized_user": current_user.user_id,
        "message": f"Successfully processed benchmark dataset '{dataset_id}'. Ingested {total_records} records.",
        "records_ingested": total_records,
        "results": results,
    }


@router.get("/benchmarks/sources/{source_id}", summary="Get detailed source documentation and blocker status")
def get_benchmark_source_detail(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Retrieves full documentation, licensing, checksums, and blocker details for a specific public dataset."""
    from app.services.dataset_service import get_dataset_registry_and_readiness
    readiness = get_dataset_registry_and_readiness(db)
    for src in readiness.get("sources", []):
        if src.get("id") == source_id.lower().strip():
            return src

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Benchmark dataset source '{source_id}' not found.",
    )


@router.get("/{run_id}", response_model=ImportRunSummaryResponse, summary="Get import run details")
def get_import_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Retrieves specific import run details and validation summary with tenant scoping."""
    run = db.query(ImportRun).filter(ImportRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Import run '{run_id}' not found.")

    if current_user.role != "admin" and run.org_id and run.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Import run '{run_id}' not found.")

    errs = db.query(ImportRowError).filter(ImportRowError.run_id == run_id).all()
    return ImportRunSummaryResponse(
        run_id=run.run_id,
        dataset_type=run.dataset_type,
        filename=run.filename,
        file_format=run.file_format,
        file_size_bytes=run.file_size_bytes,
        total_rows=run.total_rows,
        valid_rows=run.valid_rows,
        rejected_rows=run.rejected_rows,
        status=run.status,
        snapshot_id=run.snapshot_id,
        created_at=run.created_at,
        errors=[ImportRowErrorSchema.model_validate(e) for e in errs],
    )


@router.get("/{run_id}/errors", response_model=List[ImportRowErrorSchema], summary="Get row-level validation errors")
def get_import_run_errors(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Retrieves all row-level validation errors for an import execution with tenant isolation."""
    run = db.query(ImportRun).filter(ImportRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Import run '{run_id}' not found.")

    if current_user.role != "admin" and run.org_id and run.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Import run '{run_id}' not found.")

    errs = db.query(ImportRowError).filter(ImportRowError.run_id == run_id).order_by(ImportRowError.row_index.asc()).all()
    return [ImportRowErrorSchema.model_validate(e) for e in errs]


@router.get("/{run_id}/errors.csv", summary="Download row-level validation errors as CSV")
def download_import_run_errors_csv(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Downloads row-level validation errors for an import execution as a formatted CSV with recommended corrections."""
    run = db.query(ImportRun).filter(ImportRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Import run '{run_id}' not found.")

    if current_user.role != "admin" and run.org_id and run.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Import run '{run_id}' not found.")

    errs = db.query(ImportRowError).filter(ImportRowError.run_id == run_id).order_by(ImportRowError.row_index.asc()).all()

    import io
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["row_number", "field_name", "rejected_value", "error_reason", "error_code", "recommended_correction"])

    for e in errs:
        corr = "Check format and re-upload"
        if e.error_code == "MISSING_FIELD":
            corr = f"Provide non-empty value for {e.field_name}"
        elif e.error_code == "NEGATIVE_QUANTITY":
            corr = f"Ensure {e.field_name} is non-negative (>= 0)"
        elif e.error_code in ("UNKNOWN_PRODUCT", "UNKNOWN_LOCATION", "UNKNOWN_CARRIER"):
            corr = f"Verify {e.field_name} exists in master table before importing"
        elif e.error_code == "DUPLICATE_KEY":
            corr = "Ensure unique primary/business key"

        writer.writerow([e.row_index, e.field_name or "", e.rejected_value or "", e.error_reason, e.error_code, corr])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=StockWise_import_errors_{run_id}.csv"}
    )


