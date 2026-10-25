import csv
import io
import os
from typing import List, Dict, Any, Tuple
from fastapi import UploadFile, HTTPException, status
import openpyxl

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit


class FileParsingError(Exception):
    def __init__(self, message: str, code: str = "FILE_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


def validate_file_metadata(file: UploadFile) -> str:
    """Validates filename, extension, and non-empty content."""
    filename = file.filename or ""
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename."
        )

    _, ext = os.path.splitext(filename.lower())
    if ext not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Only CSV (.csv) and Excel (.xlsx, .xls) files are accepted."
        )

    return "csv" if ext == ".csv" else "xlsx"


async def parse_uploaded_file(file: UploadFile) -> Tuple[List[Dict[str, Any]], str, int]:
    """
    Safely reads and parses CSV or Excel into normalized row dictionaries.
    Returns: (rows, file_format, file_size_bytes)
    """
    file_format = validate_file_metadata(file)

    # Read file content safely
    content = await file.read()
    file_size_bytes = len(content)

    if file_size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (0 bytes)."
        )

    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of 10 MB ({round(file_size_bytes / (1024 * 1024), 2)} MB uploaded)."
        )

    if file_format == "csv":
        rows = parse_csv_content(content)
    else:
        rows = parse_excel_content(content)

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data rows found in the uploaded file (only headers or blank lines present)."
        )

    return rows, file_format, file_size_bytes


def parse_csv_content(content: bytes) -> List[Dict[str, Any]]:
    """Decodes and parses CSV content with robust encoding fallbacks."""
    text_content = None
    for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
        try:
            text_content = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if text_content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to decode CSV file. Please ensure it is saved in UTF-8 format."
        )

    # Sniff delimiter or default to comma
    sample = text_content[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except Exception:
        dialect = csv.excel

    reader = csv.reader(io.StringIO(text_content), dialect=dialect)
    try:
        raw_headers = next(reader, None)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed CSV header row: {str(exc)}"
        )

    if not raw_headers:
        return []

    # Clean header names (lowercase, stripped, remove quotes)
    headers = [h.strip().lower().replace(" ", "_") for h in raw_headers]

    rows: List[Dict[str, Any]] = []
    # 1-indexed: row 1 is header, first data row is row 2
    row_num = 1
    for raw_row in reader:
        row_num += 1
        # Skip completely blank lines
        if not raw_row or all(cell.strip() == "" for cell in raw_row):
            continue

        row_dict: Dict[str, Any] = {"_row_num": row_num}
        for i, header in enumerate(headers):
            val = raw_row[i].strip() if i < len(raw_row) else ""
            row_dict[header] = val
        rows.append(row_dict)

    return rows


def parse_excel_content(content: bytes) -> List[Dict[str, Any]]:
    """Parses Excel (.xlsx) files using openpyxl."""
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to read Excel file: {str(exc)}"
        )

    sheet = workbook.active
    if sheet is None:
        return []

    rows_iter = sheet.iter_rows(values_only=True)
    raw_headers = next(rows_iter, None)
    if not raw_headers:
        return []

    headers = [str(h).strip().lower().replace(" ", "_") if h is not None else f"col_{i}" for i, h in enumerate(raw_headers)]

    rows: List[Dict[str, Any]] = []
    row_num = 1
    for raw_row in rows_iter:
        row_num += 1
        if not raw_row or all(cell is None or str(cell).strip() == "" for cell in raw_row):
            continue

        row_dict: Dict[str, Any] = {"_row_num": row_num}
        for i, header in enumerate(headers):
            val = raw_row[i] if i < len(raw_row) else None
            # Normalize cell value to string/number
            if val is None:
                val = ""
            elif isinstance(val, (int, float)):
                val = val
            else:
                val = str(val).strip()
            row_dict[header] = val
        rows.append(row_dict)

    return rows
