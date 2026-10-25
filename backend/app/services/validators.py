from datetime import datetime, date
from typing import List, Dict, Any, Tuple, Set, Optional
from sqlalchemy.orm import Session
from app.models.entities import Product, Location, Organization

DATASET_TYPES = ["products", "locations", "inventory", "sales", "routes", "organizations"]



class ValidationError:
    def __init__(
        self,
        row_index: int,
        field_name: Optional[str],
        rejected_value: Any,
        error_reason: str,
        error_code: str,
    ):
        self.row_index = row_index
        self.field_name = field_name
        self.rejected_value = str(rejected_value) if rejected_value is not None else ""
        self.error_reason = error_reason
        self.error_code = error_code

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_index": self.row_index,
            "field_name": self.field_name,
            "rejected_value": self.rejected_value,
            "error_reason": self.error_reason,
            "error_code": self.error_code,
        }


def validate_and_parse_float(
    value: Any,
    field_name: str,
    row_index: int,
    allow_negative: bool = False,
    default: Optional[float] = None,
    required: bool = True,
) -> Tuple[Optional[float], Optional[ValidationError]]:
    if value is None or str(value).strip() == "":
        if default is not None:
            return default, None
        if not required:
            return None, None
        return None, ValidationError(
            row_index=row_index,
            field_name=field_name,
            rejected_value=value,
            error_reason=f"Field '{field_name}' cannot be empty.",
            error_code="MISSING_FIELD",
        )

    try:
        cleaned_val = str(value).replace(",", "").strip()
        num = float(cleaned_val)
    except (ValueError, TypeError):
        return None, ValidationError(
            row_index=row_index,
            field_name=field_name,
            rejected_value=value,
            error_reason=f"Field '{field_name}' must be a valid numeric number.",
            error_code="INVALID_NUMERIC",
        )

    if not allow_negative and num < 0:
        return None, ValidationError(
            row_index=row_index,
            field_name=field_name,
            rejected_value=value,
            error_reason=f"Field '{field_name}' cannot be negative ({num}).",
            error_code="NEGATIVE_QUANTITY",
        )

    return num, None


def validate_and_parse_int(
    value: Any,
    field_name: str,
    row_index: int,
    min_value: Optional[int] = None,
    default: Optional[int] = None,
) -> Tuple[Optional[int], Optional[ValidationError]]:
    if value is None or str(value).strip() == "":
        if default is not None:
            return default, None
        return None, ValidationError(
            row_index=row_index,
            field_name=field_name,
            rejected_value=value,
            error_reason=f"Field '{field_name}' cannot be empty.",
            error_code="MISSING_FIELD",
        )

    try:
        cleaned_val = str(value).replace(",", "").strip()
        num = int(float(cleaned_val))
    except (ValueError, TypeError):
        return None, ValidationError(
            row_index=row_index,
            field_name=field_name,
            rejected_value=value,
            error_reason=f"Field '{field_name}' must be a valid integer.",
            error_code="INVALID_INTEGER",
        )

    if min_value is not None and num < min_value:
        return None, ValidationError(
            row_index=row_index,
            field_name=field_name,
            rejected_value=value,
            error_reason=f"Field '{field_name}' must be at least {min_value} (got {num}).",
            error_code="VALUE_TOO_LOW",
        )

    return num, None


def validate_and_parse_date(
    value: Any,
    field_name: str,
    row_index: int,
    default: Optional[date] = None,
) -> Tuple[Optional[date], Optional[ValidationError]]:
    if value is None or str(value).strip() == "":
        if default is not None:
            return default, None
        return None, ValidationError(
            row_index=row_index,
            field_name=field_name,
            rejected_value=value,
            error_reason=f"Date field '{field_name}' cannot be empty.",
            error_code="MISSING_DATE",
        )

    if isinstance(value, datetime):
        return value.date(), None
    if isinstance(value, date):
        return value, None

    date_str = str(value).strip()
    # Try various formats
    formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y"]
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt).date()
            return parsed, None
        except ValueError:
            continue

    return None, ValidationError(
        row_index=row_index,
        field_name=field_name,
        rejected_value=value,
        error_reason=f"Date '{value}' in field '{field_name}' is not in a valid format (expected YYYY-MM-DD).",
        error_code="INVALID_DATE_FORMAT",
    )


def validate_products_dataset(
    rows: List[Dict[str, Any]],
    db: Session,
) -> Tuple[List[Dict[str, Any]], List[ValidationError]]:
    valid_records: List[Dict[str, Any]] = []
    errors: List[ValidationError] = []
    seen_skus: Set[str] = set()

    if not rows:
        return [], []

    EXPECTED_PRODUCTS_HEADERS_HELP = (
        "Expected canonical headers: sku_id, name, unit, case_pack, category (opt), shelf_life_days (opt). "
        "(supported aliases: sku, product_id, item_id, item_code, description, product_name)."
    )

    all_headers: Set[str] = {
        str(k).strip().lower().replace(" ", "_")
        for raw_row in rows
        for k in raw_row.keys()
        if k != "_row_num"
    }

    if not any(h in all_headers for h in ["sku_id", "sku", "product_id", "item_id", "item_code", "material_id", "code"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="sku_id",
            rejected_value=None,
            error_reason=f"Missing required column 'sku_id'. {EXPECTED_PRODUCTS_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    if not any(h in all_headers for h in ["name", "product_name", "description", "item_name", "title"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="name",
            rejected_value=None,
            error_reason=f"Missing required column 'name'. {EXPECTED_PRODUCTS_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    if errors:
        return [], errors

    for row in rows:
        row_num = row.get("_row_num", 0)
        sku_id = (row.get("sku_id") or row.get("sku") or "").strip()
        name = (row.get("name") or row.get("product_name") or row.get("description") or "").strip()
        category = (row.get("category") or "").strip() or "General"
        unit = (row.get("unit") or "").strip() or "cases"

        row_errors: List[ValidationError] = []

        if not sku_id:
            row_errors.append(ValidationError(row_num, "sku_id", sku_id, "Product SKU ID is required.", "MISSING_FIELD"))
        elif sku_id in seen_skus:
            row_errors.append(ValidationError(row_num, "sku_id", sku_id, f"Duplicate SKU ID '{sku_id}' found in upload.", "DUPLICATE_KEY"))
        else:
            seen_skus.add(sku_id)

        if not name:
            row_errors.append(ValidationError(row_num, "name", name, "Product name/description is required.", "MISSING_FIELD"))

        # Case pack (must be integer >= 1)
        raw_pack = row.get("case_pack")
        case_pack, pack_err = validate_and_parse_int(raw_pack, "case_pack", row_num, min_value=1, default=1)
        if pack_err:
            row_errors.append(pack_err)

        # Shelf life days (optional, but if present must be >= 0)
        raw_life = row.get("shelf_life_days") or row.get("shelf_life")
        shelf_life_days, life_err = validate_and_parse_int(raw_life, "shelf_life_days", row_num, min_value=0, default=None)
        if life_err and raw_life != "" and raw_life is not None:
            row_errors.append(life_err)

        if row_errors:
            errors.extend(row_errors)
        else:
            valid_records.append({
                "sku_id": sku_id,
                "name": name,
                "category": category,
                "unit": unit,
                "case_pack": case_pack,
                "shelf_life_days": shelf_life_days,
            })

    return valid_records, errors


def validate_organizations_dataset(
    rows: List[Dict[str, Any]],
    db: Session,
) -> Tuple[List[Dict[str, Any]], List[ValidationError]]:
    valid_records: List[Dict[str, Any]] = []
    errors: List[ValidationError] = []
    seen_orgs: Set[str] = set()

    if not rows:
        return [], []

    EXPECTED_ORGS_HEADERS_HELP = (
        "Expected canonical headers: org_id, name, org_type, contact_email (opt), contact_phone (opt). "
        "(supported aliases: id, organization_id, org_name, type)."
    )

    all_headers: Set[str] = {
        str(k).strip().lower().replace(" ", "_")
        for raw_row in rows
        for k in raw_row.keys()
        if k != "_row_num"
    }

    if not any(h in all_headers for h in ["org_id", "id", "organization_id", "company_id"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="org_id",
            rejected_value=None,
            error_reason=f"Missing required column 'org_id'. {EXPECTED_ORGS_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    if not any(h in all_headers for h in ["name", "org_name", "company_name"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="name",
            rejected_value=None,
            error_reason=f"Missing required column 'name'. {EXPECTED_ORGS_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    if not any(h in all_headers for h in ["org_type", "type", "organization_type"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="org_type",
            rejected_value=None,
            error_reason=f"Missing required column 'org_type'. {EXPECTED_ORGS_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    if errors:
        return [], errors

    VALID_ORG_TYPES = {
        "fmcg_company",
        "cnf_agency",
        "logistics_provider",
        "distributor",
        "retailer",
    }

    for row in rows:
        row_num = row.get("_row_num", 0)
        org_id = (row.get("org_id") or row.get("id") or "").strip()
        name = (row.get("name") or row.get("org_name") or "").strip()
        raw_type = (row.get("org_type") or row.get("type") or "").strip().lower()
        contact_email = (row.get("contact_email") or row.get("email") or "").strip() or None
        contact_phone = (row.get("contact_phone") or row.get("phone") or "").strip() or None
        raw_active = row.get("is_active")

        row_errors: List[ValidationError] = []

        if not org_id:
            row_errors.append(ValidationError(row_num, "org_id", org_id, "Organization ID is required.", "MISSING_FIELD"))
        elif org_id in seen_orgs:
            row_errors.append(ValidationError(row_num, "org_id", org_id, f"Duplicate Organization ID '{org_id}' found in upload.", "DUPLICATE_KEY"))
        else:
            seen_orgs.add(org_id)

        if not name:
            row_errors.append(ValidationError(row_num, "name", name, "Organization name is required.", "MISSING_FIELD"))

        if not raw_type:
            row_errors.append(ValidationError(row_num, "org_type", raw_type, "Organization type is required.", "MISSING_FIELD"))
        elif raw_type not in VALID_ORG_TYPES:
            row_errors.append(ValidationError(
                row_num, "org_type", raw_type,
                f"Invalid organization type '{raw_type}'. Allowed: {', '.join(sorted(list(VALID_ORG_TYPES)))}",
                "INVALID_ORG_TYPE"
            ))

        is_active = True
        if raw_active is not None:
            str_act = str(raw_active).strip().lower()
            if str_act in ["false", "0", "no", "inactive"]:
                is_active = False

        if row_errors:
            errors.extend(row_errors)
        else:
            valid_records.append({
                "org_id": org_id,
                "name": name,
                "org_type": raw_type,
                "contact_email": contact_email,
                "contact_phone": contact_phone,
                "is_active": is_active,
            })

    return valid_records, errors


VALID_LOCATION_TYPES: Set[str] = {
    "manufacturing_plant",
    "central_warehouse",
    "company_warehouse",
    "regional_warehouse",
    "cnf_facility",
    "3pl_facility",
    "distributor_warehouse",
    "retail_destination",
}

LOCATION_TYPE_ALIASES: Dict[str, str] = {
    "plant": "manufacturing_plant",
    "factory": "manufacturing_plant",
    "manufacturing": "manufacturing_plant",
    "central_dc": "central_warehouse",
    "cdc": "central_warehouse",
    "company_dc": "company_warehouse",
    "regional_dc": "regional_warehouse",
    "rdc": "regional_warehouse",
    "cnf": "cnf_facility",
    "c&f": "cnf_facility",
    "3pl": "3pl_facility",
    "distributor": "distributor_warehouse",
    "distributor_hub": "distributor_warehouse",
    "retailer": "retail_destination",
    "retail": "retail_destination",
    "retail_store": "retail_destination",
    "store": "retail_destination",
    "warehouse": "company_warehouse",
}


def validate_locations_dataset(
    rows: List[Dict[str, Any]],
    db: Session,
) -> Tuple[List[Dict[str, Any]], List[ValidationError]]:
    valid_records: List[Dict[str, Any]] = []
    errors: List[ValidationError] = []
    seen_locations: Set[str] = set()

    if not rows:
        return valid_records, errors

    # Check header-level presence of required columns across uploaded dataset
    file_headers = {str(k).strip().lower().replace(" ", "_") for k in rows[0].keys() if k != "_row_num"}

    # Canonical required fields and their supported column aliases
    has_region = any(h in file_headers for h in ["region", "location_region", "zone", "territory", "area"])
    has_loc_id = any(h in file_headers for h in ["location_id", "id", "facility_id", "loc_id", "site_id", "code", "node_id"])
    has_name = any(h in file_headers for h in ["name", "location_name", "facility_name", "site_name", "node_name"])
    has_type = any(h in file_headers for h in ["location_type", "type", "facility_type", "site_type", "node_type"])

    EXPECTED_HEADERS_HELP = (
        "Expected canonical headers: location_id, name, location_type, region, city, address, "
        "owner_org_id, operator_org_id, storage_capacity_units, dispatch_capacity_daily, is_active. "
        "Download the official template via GET /api/imports/templates/locations."
    )

    if not has_region:
        errors.append(ValidationError(
            row_index=1,
            field_name="region",
            rejected_value=None,
            error_reason=f"Missing required column 'region'. The uploaded file header does not contain the 'region' column. {EXPECTED_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))
    if not has_loc_id:
        errors.append(ValidationError(
            row_index=1,
            field_name="location_id",
            rejected_value=None,
            error_reason=f"Missing required column 'location_id'. {EXPECTED_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))
    if not has_name:
        errors.append(ValidationError(
            row_index=1,
            field_name="name",
            rejected_value=None,
            error_reason=f"Missing required column 'name'. {EXPECTED_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))
    if not has_type:
        errors.append(ValidationError(
            row_index=1,
            field_name="location_type",
            rejected_value=None,
            error_reason=f"Missing required column 'location_type'. {EXPECTED_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    # If any required column is completely missing from the file header, quarantine immediately
    if errors:
        return [], errors

    # Pre-fetch existing valid Organizations for referential integrity
    existing_orgs = set(org for (org,) in db.query(Organization.org_id).all())

    for raw_row in rows:
        row = {str(k).strip().lower().replace(" ", "_"): v for k, v in raw_row.items() if k != "_row_num"}
        row_num = raw_row.get("_row_num", 0)
        location_id = (
            row.get("location_id") or row.get("id") or row.get("facility_id") or row.get("loc_id") or row.get("site_id") or row.get("node_id") or ""
        ).strip()
        name = (
            row.get("name") or row.get("location_name") or row.get("facility_name") or row.get("site_name") or row.get("node_name") or ""
        ).strip()
        raw_type = (
            row.get("location_type") or row.get("type") or row.get("facility_type") or row.get("site_type") or row.get("node_type") or ""
        ).strip().lower()

        # Safely extract region with supported aliases (state is NOT an alias for region)
        region = (
            row.get("region")
            or row.get("location_region")
            or row.get("zone")
            or row.get("territory")
            or row.get("area")
            or ""
        ).strip()

        city = (row.get("city") or row.get("town") or row.get("district") or "").strip() or None
        raw_address = (row.get("address") or row.get("street_address") or row.get("location_address") or row.get("address_line") or "").strip() or None
        raw_state = (row.get("state") or row.get("province") or "").strip()
        if not raw_address and raw_state:
            address = f"{city}, {raw_state}" if city else raw_state
        else:
            address = raw_address

        owner_org_id = (row.get("owner_org_id") or row.get("owner_org") or row.get("owner_id") or row.get("owner") or "").strip() or None
        operator_org_id = (row.get("operator_org_id") or row.get("operator_org") or row.get("operator_id") or row.get("operator") or "").strip() or None

        row_errors: List[ValidationError] = []

        if not location_id:
            row_errors.append(ValidationError(row_num, "location_id", location_id, "Location ID is required.", "MISSING_FIELD"))
        elif location_id in seen_locations:
            row_errors.append(ValidationError(row_num, "location_id", location_id, f"Duplicate Location ID '{location_id}' found in upload.", "DUPLICATE_KEY"))
        else:
            seen_locations.add(location_id)

        if not name:
            row_errors.append(ValidationError(row_num, "name", name, "Location name is required.", "MISSING_FIELD"))

        # Location type normalization and validation
        if not raw_type:
            row_errors.append(ValidationError(row_num, "location_type", raw_type, "Location type is required.", "MISSING_FIELD"))
            normalized_type = raw_type
        else:
            normalized_type = LOCATION_TYPE_ALIASES.get(raw_type, raw_type)
            if normalized_type not in VALID_LOCATION_TYPES:
                row_errors.append(ValidationError(
                    row_num, "location_type", raw_type,
                    f"Invalid location type '{raw_type}'. Allowed types: {', '.join(sorted(VALID_LOCATION_TYPES))}.",
                    "INVALID_LOCATION_TYPE",
                ))

        # Region validation: row-level MISSING_FIELD when blank
        if not region:
            row_errors.append(ValidationError(row_num, "region", region, "Location region is required.", "MISSING_FIELD"))

        # Check organization references if provided
        if owner_org_id and existing_orgs and owner_org_id not in existing_orgs:
            row_errors.append(ValidationError(
                row_num, "owner_org_id", owner_org_id,
                f"Unknown Owning Organization '{owner_org_id}'. Organization master record does not exist.",
                "UNKNOWN_ORGANIZATION"
            ))

        if operator_org_id and existing_orgs and operator_org_id not in existing_orgs:
            row_errors.append(ValidationError(
                row_num, "operator_org_id", operator_org_id,
                f"Unknown Operating Organization '{operator_org_id}'. Organization master record does not exist.",
                "UNKNOWN_ORGANIZATION"
            ))

        storage_cap, sc_err = validate_and_parse_float(
            row.get("storage_capacity_units") or row.get("storage_capacity") or row.get("capacity_units") or row.get("capacity"),
            "storage_capacity_units",
            row_num,
            allow_negative=False,
            default=None,
            required=False,
        )
        if sc_err:
            row_errors.append(sc_err)

        dispatch_cap, dc_err = validate_and_parse_float(
            row.get("dispatch_capacity_daily") or row.get("dispatch_capacity") or row.get("daily_dispatch_capacity") or row.get("daily_capacity"),
            "dispatch_capacity_daily",
            row_num,
            allow_negative=False,
            default=None,
            required=False,
        )
        if dc_err:
            row_errors.append(dc_err)

        lat, lat_err = validate_and_parse_float(
            row.get("latitude") or row.get("lat") or row.get("geo_lat"),
            "latitude",
            row_num,
            allow_negative=True,
            default=None,
            required=False,
        )
        if lat_err:
            row_errors.append(lat_err)

        lon, lon_err = validate_and_parse_float(
            row.get("longitude") or row.get("lon") or row.get("lng") or row.get("geo_lon") or row.get("geo_lng"),
            "longitude",
            row_num,
            allow_negative=True,
            default=None,
            required=False,
        )
        if lon_err:
            row_errors.append(lon_err)

        is_active = True
        raw_act = row.get("is_active") or row.get("active") or row.get("status")
        if raw_act is not None and str(raw_act).strip().lower() in ["false", "0", "no", "inactive"]:
            is_active = False

        if row_errors:
            errors.extend(row_errors)
        else:
            valid_records.append({
                "location_id": location_id,
                "name": name,
                "location_type": normalized_type,
                "region": region,
                "city": city,
                "address": address,
                "owner_org_id": owner_org_id,
                "operator_org_id": operator_org_id,
                "storage_capacity_units": storage_cap,
                "dispatch_capacity_daily": dispatch_cap,
                "latitude": lat,
                "longitude": lon,
                "is_active": is_active,
            })

    return valid_records, errors



def validate_inventory_dataset(
    rows: List[Dict[str, Any]],
    db: Session,
    default_snapshot_id: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[ValidationError]]:
    valid_records: List[Dict[str, Any]] = []
    errors: List[ValidationError] = []
    seen_compound_keys: Set[Tuple[str, str, str]] = set()

    if not rows:
        return [], []

    EXPECTED_INVENTORY_HEADERS_HELP = (
        "Expected canonical headers: snapshot_id, sku_id, location_id, on_hand, reserved (opt), blocked (opt), "
        "confirmed_incoming (opt), as_of_date (opt), expiry_date (opt), batch_number (opt), owner_org_id (opt). "
        "(supported aliases: sku, product_id, facility_id, warehouse_id, qty_on_hand, stock)."
    )

    all_headers: Set[str] = {
        str(k).strip().lower().replace(" ", "_")
        for raw_row in rows
        for k in raw_row.keys()
        if k != "_row_num"
    }

    if not any(h in all_headers for h in ["sku_id", "sku", "product_id", "item_id", "item_code"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="sku_id",
            rejected_value=None,
            error_reason=f"Missing required column 'sku_id'. {EXPECTED_INVENTORY_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    if not any(h in all_headers for h in ["location_id", "location", "facility_id", "loc_id", "warehouse_id", "wh_id"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="location_id",
            rejected_value=None,
            error_reason=f"Missing required column 'location_id'. {EXPECTED_INVENTORY_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    if not any(h in all_headers for h in ["on_hand", "on_hand_units", "on_hand_qty", "qty_on_hand", "stock_on_hand", "stock", "quantity", "inventory"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="on_hand",
            rejected_value=None,
            error_reason=f"Missing required column 'on_hand'. {EXPECTED_INVENTORY_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    if errors:
        return [], errors

    # Pre-fetch existing valid SKUs, Locations, and Organizations for referential integrity
    existing_skus = set(sku for (sku,) in db.query(Product.sku_id).all())
    existing_locations = set(loc for (loc,) in db.query(Location.location_id).all())
    existing_orgs = set(org for (org,) in db.query(Organization.org_id).all())

    default_as_of = date.today()

    for raw_row in rows:
        row = {str(k).strip().lower().replace(" ", "_"): v for k, v in raw_row.items() if k != "_row_num"}
        row_num = raw_row.get("_row_num", 0)
        snapshot_id = (row.get("snapshot_id") or row.get("snapshot") or default_snapshot_id or "SNAP-DEFAULT").strip()
        sku_id = (row.get("sku_id") or row.get("sku") or row.get("product_id") or row.get("item_id") or row.get("item_code") or "").strip()
        location_id = (row.get("location_id") or row.get("location") or row.get("facility_id") or row.get("loc_id") or row.get("warehouse_id") or "").strip()
        owner_org_id = (row.get("owner_org_id") or row.get("owner_org") or row.get("owner_id") or row.get("org_id") or "").strip() or None
        batch_number = (row.get("batch_number") or row.get("batch") or row.get("lot_number") or row.get("lot") or "").strip() or None

        row_errors: List[ValidationError] = []

        # Identifier checks
        if not sku_id:
            row_errors.append(ValidationError(row_num, "sku_id", sku_id, "SKU ID is required.", "MISSING_FIELD"))
        elif sku_id not in existing_skus:
            row_errors.append(ValidationError(
                row_num, "sku_id", sku_id,
                f"Unknown SKU '{sku_id}'. Product master record does not exist. Please import Products/SKUs first.",
                "UNKNOWN_SKU"
            ))

        if not location_id:
            row_errors.append(ValidationError(row_num, "location_id", location_id, "Location ID is required.", "MISSING_FIELD"))
        elif location_id not in existing_locations:
            row_errors.append(ValidationError(
                row_num, "location_id", location_id,
                f"Unknown Location '{location_id}'. Location master record does not exist. Please import Network Locations first.",
                "UNKNOWN_LOCATION"
            ))

        if owner_org_id and existing_orgs and owner_org_id not in existing_orgs:
            row_errors.append(ValidationError(
                row_num, "owner_org_id", owner_org_id,
                f"Unknown Owning Organization '{owner_org_id}'. Organization master record does not exist.",
                "UNKNOWN_ORGANIZATION"
            ))

        compound_key = (snapshot_id, sku_id, location_id)
        if sku_id and location_id:
            if compound_key in seen_compound_keys:
                row_errors.append(ValidationError(
                    row_num, "sku_id", f"{sku_id}@{location_id}",
                    f"Duplicate inventory record for SKU '{sku_id}' at location '{location_id}' in snapshot '{snapshot_id}'.",
                    "DUPLICATE_KEY"
                ))
            else:
                seen_compound_keys.add(compound_key)

        # Quantitative checks
        raw_oh = row.get("on_hand") or row.get("on_hand_units") or row.get("on_hand_qty") or row.get("qty_on_hand") or row.get("stock_on_hand") or row.get("stock") or row.get("quantity") or row.get("inventory")
        on_hand, oh_err = validate_and_parse_float(raw_oh, "on_hand", row_num, allow_negative=False)
        if oh_err:
            row_errors.append(oh_err)

        raw_res = row.get("reserved") or row.get("reserved_units") or row.get("reserved_qty") or row.get("qty_reserved") or row.get("allocated")
        reserved, res_err = validate_and_parse_float(raw_res, "reserved", row_num, allow_negative=False, default=0.0)
        if res_err:
            row_errors.append(res_err)

        raw_blk = row.get("blocked") or row.get("blocked_units") or row.get("blocked_qty") or row.get("qty_blocked") or row.get("damaged") or row.get("quarantine")
        blocked, blk_err = validate_and_parse_float(raw_blk, "blocked", row_num, allow_negative=False, default=0.0)
        if blk_err:
            row_errors.append(blk_err)

        raw_inc = row.get("confirmed_incoming") or row.get("incoming") or row.get("in_transit") or row.get("incoming_units") or row.get("pipeline")
        incoming, inc_err = validate_and_parse_float(raw_inc, "confirmed_incoming", row_num, allow_negative=False, default=0.0)
        if inc_err:
            row_errors.append(inc_err)

        as_of, date_err = validate_and_parse_date(row.get("as_of_date") or row.get("date") or row.get("snapshot_date"), "as_of_date", row_num, default=default_as_of)
        if date_err:
            row_errors.append(date_err)

        expiry_date = None
        raw_expiry = row.get("expiry_date") or row.get("expiry") or row.get("expiration_date") or row.get("best_before")
        if raw_expiry not in [None, ""]:
            expiry_date, exp_err = validate_and_parse_date(raw_expiry, "expiry_date", row_num, default=None)
            if exp_err:
                row_errors.append(exp_err)

        if row_errors:
            errors.extend(row_errors)
        else:
            valid_records.append({
                "snapshot_id": snapshot_id,
                "sku_id": sku_id,
                "location_id": location_id,
                "owner_org_id": owner_org_id,
                "on_hand": on_hand or 0.0,
                "reserved": reserved or 0.0,
                "blocked": blocked or 0.0,
                "confirmed_incoming": incoming or 0.0,
                "batch_number": batch_number,
                "expiry_date": expiry_date,
                "as_of_date": as_of or default_as_of,
            })

    return valid_records, errors


def validate_sales_dataset(
    rows: List[Dict[str, Any]],
    db: Session,
) -> Tuple[List[Dict[str, Any]], List[ValidationError]]:
    valid_records: List[Dict[str, Any]] = []
    errors: List[ValidationError] = []
    seen_compound_keys: Set[Tuple[str, str, str]] = set()

    if not rows:
        return [], []

    EXPECTED_SALES_HEADERS_HELP = (
        "Expected canonical headers: sku_id, location_id (or destination_id), sales_date, quantity "
        "(supported aliases: quantity_sold, units_sold, sales_quantity, demand_units, units, qty, sales_volume, volume)."
    )

    # File-level header check for missing required columns
    all_headers: Set[str] = set()
    for raw_row in rows:
        for k in raw_row.keys():
            if k != "_row_num":
                all_headers.add(str(k).strip().lower().replace(" ", "_"))

    # 1. Check SKU column
    if not any(h in all_headers for h in ["sku_id", "sku", "product_id", "item_id", "item_code", "material_id", "code"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="sku_id",
            rejected_value=None,
            error_reason=f"Missing required column 'sku_id'. {EXPECTED_SALES_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    # 2. Check Destination/Location column
    if not any(h in all_headers for h in ["destination_id", "location_id", "destination", "location", "dest_id", "dest_loc", "store_id", "retailer_id", "customer_id"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="location_id",
            rejected_value=None,
            error_reason=f"Missing required column 'location_id' (or 'destination_id'). {EXPECTED_SALES_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    # 3. Check Sales Date column
    if not any(h in all_headers for h in ["sales_date", "date", "demand_date", "sale_date", "transaction_date", "order_date", "invoice_date"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="sales_date",
            rejected_value=None,
            error_reason=f"Missing required column 'sales_date'. {EXPECTED_SALES_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    qty_keys = [
        "quantity", "quantity_sold", "units_sold", "sales_quantity", "demand_units",
        "units", "sales_qty", "qty", "sales_volume", "volume", "sales", "demand",
        "cases", "units_demanded", "quantity_cases", "order_quantity", "sold_qty",
    ]
    if not any(h in all_headers for h in qty_keys):
        errors.append(ValidationError(
            row_index=1,
            field_name="quantity",
            rejected_value=None,
            error_reason=f"Missing required column 'quantity' (or aliases: quantity_sold, units_sold, sales_quantity, volume). {EXPECTED_SALES_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    # If any required column is completely missing from file header, quarantine file immediately
    if errors:
        return [], errors

    existing_skus = set(sku for (sku,) in db.query(Product.sku_id).all())
    existing_locations = set(loc for (loc,) in db.query(Location.location_id).all())

    for raw_row in rows:
        row = {str(k).strip().lower().replace(" ", "_"): v for k, v in raw_row.items() if k != "_row_num"}
        row_num = raw_row.get("_row_num", 0)
        sku_id = (
            row.get("sku_id")
            or row.get("sku")
            or row.get("product_id")
            or row.get("item_id")
            or row.get("item_code")
            or row.get("material_id")
            or row.get("code")
            or ""
        ).strip()
        destination_id = (
            row.get("destination_id")
            or row.get("location_id")
            or row.get("destination")
            or row.get("location")
            or row.get("dest_id")
            or row.get("dest_loc")
            or row.get("store_id")
            or row.get("retailer_id")
            or row.get("customer_id")
            or ""
        ).strip()

        row_errors: List[ValidationError] = []

        if not sku_id:
            row_errors.append(ValidationError(row_num, "sku_id", sku_id, "SKU ID is required.", "MISSING_FIELD"))
        elif sku_id not in existing_skus:
            row_errors.append(ValidationError(
                row_num, "sku_id", sku_id,
                f"Unknown SKU '{sku_id}'. Product master record does not exist. Please import Products/SKUs first.",
                "UNKNOWN_SKU"
            ))

        if not destination_id:
            row_errors.append(ValidationError(row_num, "destination_id", destination_id, "Destination Location ID is required.", "MISSING_FIELD"))
        elif destination_id not in existing_locations:
            row_errors.append(ValidationError(
                row_num, "destination_id", destination_id,
                f"Unknown Destination Location '{destination_id}'. Location master record does not exist. Please import Network Locations first.",
                "UNKNOWN_LOCATION"
            ))

        raw_date = (
            row.get("sales_date")
            or row.get("date")
            or row.get("demand_date")
            or row.get("sale_date")
            or row.get("transaction_date")
            or row.get("order_date")
            or row.get("invoice_date")
        )
        if raw_date is None or str(raw_date).strip() == "":
            row_errors.append(ValidationError(row_num, "sales_date", raw_date, "Sales date is required.", "MISSING_FIELD"))
            sales_date = None
        else:
            sales_date, date_err = validate_and_parse_date(raw_date, "sales_date", row_num)
            if date_err:
                row_errors.append(date_err)

        if sku_id and destination_id and sales_date:
            compound_key = (sku_id, destination_id, str(sales_date))
            if compound_key in seen_compound_keys:
                row_errors.append(ValidationError(
                    row_num, "sales_date", f"{sku_id}@{destination_id} on {sales_date}",
                    f"Duplicate sales entry for SKU '{sku_id}' at destination '{destination_id}' on {sales_date}.",
                    "DUPLICATE_KEY"
                ))
            else:
                seen_compound_keys.add(compound_key)

        # Safely extract raw quantity without falling into Python 0 falsy trap
        raw_quantity = None
        for q_key in qty_keys:
            if q_key in row:
                val = row[q_key]
                if val is not None and str(val).strip() != "":
                    raw_quantity = val
                    break
        if raw_quantity is None:
            for q_key in qty_keys:
                if q_key in row:
                    raw_quantity = row[q_key]
                    break

        quantity, qty_err = validate_and_parse_float(raw_quantity, "quantity", row_num, allow_negative=False, required=True)
        if qty_err:
            row_errors.append(qty_err)

        if row_errors:
            errors.extend(row_errors)
        else:
            valid_records.append({
                "sku_id": sku_id,
                "destination_id": destination_id,
                "sales_date": sales_date,
                "quantity": float(quantity) if quantity is not None else 0.0,
            })

    return valid_records, errors


def validate_routes_dataset(
    rows: List[Dict[str, Any]],
    db: Session,
) -> Tuple[List[Dict[str, Any]], List[ValidationError]]:
    valid_records: List[Dict[str, Any]] = []
    errors: List[ValidationError] = []
    seen_route_pairs: Set[Tuple[str, str]] = set()

    if not rows:
        return [], []

    EXPECTED_ROUTES_HEADERS_HELP = (
        "Expected canonical headers: from_location_id, to_location_id, lead_time_days, cost_rate, "
        "carrier_agency_id (opt), capacity_units (opt). "
        "(supported aliases: origin_id, destination_id, transit_time_days, cost, rate)."
    )

    all_headers: Set[str] = {
        str(k).strip().lower().replace(" ", "_")
        for raw_row in rows
        for k in raw_row.keys()
        if k != "_row_num"
    }

    if not any(h in all_headers for h in ["from_location_id", "from_id", "from_location", "origin_id", "origin", "source_location_id", "source_id"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="from_location_id",
            rejected_value=None,
            error_reason=f"Missing required column 'from_location_id'. {EXPECTED_ROUTES_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    if not any(h in all_headers for h in ["to_location_id", "to_id", "to_location", "destination_location_id", "destination_id", "destination", "dest_id"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="to_location_id",
            rejected_value=None,
            error_reason=f"Missing required column 'to_location_id'. {EXPECTED_ROUTES_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    if not any(h in all_headers for h in ["lead_time_days", "lead_time", "transit_time_days", "days"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="lead_time_days",
            rejected_value=None,
            error_reason=f"Missing required column 'lead_time_days'. {EXPECTED_ROUTES_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    if not any(h in all_headers for h in ["cost_rate", "cost", "rate", "cost_per_unit", "freight_cost"]):
        errors.append(ValidationError(
            row_index=1,
            field_name="cost_rate",
            rejected_value=None,
            error_reason=f"Missing required column 'cost_rate'. {EXPECTED_ROUTES_HEADERS_HELP}",
            error_code="MISSING_COLUMN",
        ))

    if errors:
        return [], errors

    existing_locations = set(loc for (loc,) in db.query(Location.location_id).all())
    existing_orgs = set(org for (org,) in db.query(Organization.org_id).all())

    for row in rows:
        row_num = row.get("_row_num", 0)
        from_id = (
            row.get("from_location_id")
            or row.get("from_id")
            or row.get("source_location_id")
            or row.get("source_id")
            or ""
        ).strip()
        to_id = (
            row.get("to_location_id")
            or row.get("to_id")
            or row.get("destination_location_id")
            or row.get("destination_id")
            or ""
        ).strip()
        carrier_agency_id = (
            row.get("carrier_agency_id")
            or row.get("carrier_id")
            or row.get("agency_id")
            or ""
        ).strip() or None
        sku_eligibility = (row.get("sku_eligibility") or "").strip() or "all"
        pricing_basis = (row.get("pricing_basis") or "per_unit").strip().lower()

        row_errors: List[ValidationError] = []

        if not from_id:
            row_errors.append(ValidationError(row_num, "from_location_id", from_id, "Source Location ID (from_id) is required.", "MISSING_FIELD"))
        elif from_id not in existing_locations:
            row_errors.append(ValidationError(
                row_num, "from_location_id", from_id,
                f"Unknown Source Location '{from_id}'. Location master record does not exist.",
                "UNKNOWN_SOURCE_LOCATION"
            ))

        if not to_id:
            row_errors.append(ValidationError(row_num, "to_location_id", to_id, "Destination Location ID (to_id) is required.", "MISSING_FIELD"))
        elif to_id not in existing_locations:
            row_errors.append(ValidationError(
                row_num, "to_location_id", to_id,
                f"Unknown Destination Location '{to_id}'. Location master record does not exist.",
                "UNKNOWN_DESTINATION_LOCATION"
            ))

        if carrier_agency_id and carrier_agency_id not in existing_orgs:
            row_errors.append(ValidationError(
                row_num, "carrier_agency_id", carrier_agency_id,
                f"Unknown Carrier Agency '{carrier_agency_id}'. Organization master record does not exist.",
                "UNKNOWN_CARRIER_AGENCY"
            ))

        if from_id and to_id and from_id == to_id:
            row_errors.append(ValidationError(
                row_num, "to_location_id", f"{from_id}->{to_id}",
                f"Source and destination cannot be identical (self-referencing route: '{from_id}').",
                "SELF_REFERENCING_ROUTE"
            ))

        if from_id and to_id:
            route_pair = (from_id, to_id)
            if route_pair in seen_route_pairs:
                row_errors.append(ValidationError(
                    row_num, "from_location_id", f"{from_id}->{to_id}",
                    f"Duplicate route '{from_id}' to '{to_id}' found in upload.",
                    "DUPLICATE_KEY"
                ))
            else:
                seen_route_pairs.add(route_pair)

        lead_time_days, lt_err = validate_and_parse_float(row.get("lead_time_days") or row.get("lead_time"), "lead_time_days", row_num, allow_negative=False)
        if lt_err:
            row_errors.append(lt_err)
        elif lead_time_days is not None and lead_time_days <= 0:
            row_errors.append(ValidationError(
                row_num, "lead_time_days", lead_time_days,
                f"Lead time must be strictly greater than 0 (got {lead_time_days}).",
                "INVALID_LEAD_TIME"
            ))

        cost_rate, cr_err = validate_and_parse_float(
            row.get("cost_rate") or row.get("cost_per_unit") or row.get("rate") or row.get("cost"),
            "cost_rate",
            row_num,
            allow_negative=False,
        )
        if cr_err:
            row_errors.append(cr_err)

        raw_cap = row.get("capacity_units") or row.get("daily_capacity") or row.get("capacity")
        capacity_units, cap_err = validate_and_parse_float(raw_cap, "capacity_units", row_num, allow_negative=False, default=None)
        if cap_err and raw_cap != "" and raw_cap is not None:
            row_errors.append(cap_err)
        elif capacity_units is not None and capacity_units <= 0:
            row_errors.append(ValidationError(
                row_num, "capacity_units", capacity_units,
                f"Capacity must be strictly positive (got {capacity_units}).",
                "INVALID_CAPACITY"
            ))

        min_qty, _ = validate_and_parse_float(row.get("min_shipment_qty"), "min_shipment_qty", row_num, allow_negative=False, default=None)
        max_qty, _ = validate_and_parse_float(row.get("max_shipment_qty"), "max_shipment_qty", row_num, allow_negative=False, default=None)

        is_active = True
        raw_act = row.get("is_active")
        if raw_act is not None and str(raw_act).strip().lower() in ["false", "0", "no", "inactive"]:
            is_active = False

        if row_errors:
            errors.extend(row_errors)
        else:
            valid_records.append({
                "from_location_id": from_id,
                "to_location_id": to_id,
                "carrier_agency_id": carrier_agency_id,
                "lead_time_days": lead_time_days,
                "cost_rate": cost_rate,
                "capacity_units": capacity_units,
                "sku_eligibility": sku_eligibility,
                "pricing_basis": pricing_basis,
                "min_shipment_qty": min_qty,
                "max_shipment_qty": max_qty,
                "is_active": is_active,
            })

    return valid_records, errors
