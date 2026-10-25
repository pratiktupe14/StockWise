"""
StockWise Idempotency and Concurrency Locking Service.

Provides:
- Idempotent execution protection for mutating logistics and planning operations.
- Dialect-aware row-level locking (SELECT ... FOR UPDATE on PostgreSQL) to prevent concurrent race conditions.
"""

import hashlib
import json
import logging
from typing import Any, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session
from app.models.entities import IdempotencyRecord

logger = logging.getLogger("stockwise.idempotency")


def compute_request_hash(payload: Any) -> str:
    """Computes a deterministic SHA-256 hash of the request payload."""
    if isinstance(payload, dict):
        serialized = json.dumps(payload, sort_keys=True, default=str)
    elif isinstance(payload, str):
        serialized = payload
    else:
        serialized = str(payload)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def check_idempotency(
    db: Session,
    key: Optional[str],
    endpoint: str,
    request_payload: Any = None,
) -> Optional[Tuple[int, dict]]:
    """
    Checks if an idempotent operation has already been executed.
    Returns (status_code, response_data) if already processed with identical payload.
    """
    if not key:
        return None

    record = db.query(IdempotencyRecord).filter(IdempotencyRecord.key == key).first()
    if not record:
        return None

    # Verify request payload hash to prevent key reuse with mismatched arguments
    if request_payload is not None:
        incoming_hash = compute_request_hash(request_payload)
        if record.request_hash != incoming_hash:
            logger.warning(
                f"Idempotency key '{key}' reused with mismatched payload hash. "
                f"Expected {record.request_hash}, got {incoming_hash}"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Idempotency conflict: Key '{key}' was previously used with a different request payload.",
            )

    try:
        data = json.loads(record.response_data)
        logger.info(f"Replaying idempotent response for key '{key}' at {endpoint}")
        return record.status_code, data
    except Exception as err:
        logger.error(f"Failed to deserialize idempotent record for key '{key}': {err}")
        return None


def record_idempotency(
    db: Session,
    key: Optional[str],
    user_id: Optional[str],
    endpoint: str,
    request_payload: Any,
    status_code: int,
    response_data: Any,
) -> None:
    """Persists response details for future idempotent retries."""
    if not key:
        return

    try:
        req_hash = compute_request_hash(request_payload)
        serialized_resp = (
            json.dumps(response_data, default=str)
            if not isinstance(response_data, str)
            else response_data
        )

        record = IdempotencyRecord(
            key=key,
            user_id=user_id,
            endpoint=endpoint,
            request_hash=req_hash,
            status_code=status_code,
            response_data=serialized_resp,
        )
        db.merge(record)
        db.commit()
    except Exception as err:
        logger.error(f"Failed to persist idempotency key '{key}': {err}")
        db.rollback()


def with_row_lock(query: Query, db: Session) -> Query:
    """
    Applies SELECT ... FOR UPDATE on PostgreSQL to establish exclusive row locks.
    Safely bypasses locking on SQLite (in unit tests) where FOR UPDATE is unsupported.
    """
    try:
        dialect = db.bind.dialect.name if db.bind else ""
    except Exception:
        dialect = ""

    if dialect == "postgresql":
        return query.with_for_update()
    return query
