from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import IdempotencyRecord


class IdempotencyError(Exception):
    """An invalid or conflicting durable idempotency request."""


@dataclass(frozen=True)
class IdempotencyClaim:
    record: IdempotencyRecord
    replayed: bool


def request_hash(payload: object) -> str:
    """Create the canonical hash used to bind a key to one request."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


def claim_idempotency(
    db: Session,
    *,
    tenant_id: UUID,
    organization_id: UUID,
    key: str,
    operation: str,
    request_hash: str,
) -> IdempotencyClaim:
    """Atomically reserve a request key before applying its side effect.

    A response status of zero is an uncommitted reservation.  The reservation
    and the business effect are committed in the same request transaction, so
    a crashed or failed operation cannot leave a durable half-complete result.
    PostgreSQL and SQLite use an atomic conflict-free insert, allowing a
    concurrent retry to wait for the first transaction and then replay it.
    """
    normalized_key = key.strip()
    if not normalized_key or len(normalized_key) > 200:
        raise IdempotencyError("a valid idempotency key is required")

    existing = db.scalar(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.organization_id == organization_id,
            IdempotencyRecord.key == normalized_key,
        )
        .with_for_update()
    )
    if existing is not None:
        _validate_existing(existing, operation, request_hash)
        if existing.response_status == 0:
            raise IdempotencyError("idempotency request is already in progress")
        return IdempotencyClaim(existing, replayed=True)

    record_id = uuid4()
    values = {
        "id": record_id,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "tenant_id": tenant_id,
        "organization_id": organization_id,
        "key": normalized_key,
        "operation": operation,
        "request_hash": request_hash,
        "response_status": 0,
        "response_body": {},
        "resource_id": None,
    }
    dialect = db.get_bind().dialect.name
    returns_inserted_id = False
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert

        statement = dialect_insert(IdempotencyRecord).values(**values)
        statement = statement.on_conflict_do_nothing(
            index_elements=[
                IdempotencyRecord.tenant_id,
                IdempotencyRecord.organization_id,
                IdempotencyRecord.key,
            ]
        ).returning(IdempotencyRecord.id)
        returns_inserted_id = True
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert

        statement = dialect_insert(IdempotencyRecord).values(**values)
        statement = statement.on_conflict_do_nothing(
            index_elements=[
                IdempotencyRecord.tenant_id,
                IdempotencyRecord.organization_id,
                IdempotencyRecord.key,
            ]
        )
    else:
        raise IdempotencyError(
            f"idempotency is not supported for database dialect {dialect!r}"
        )

    try:
        result = db.execute(statement)
    except IntegrityError as error:
        raise IdempotencyError("could not reserve idempotency key") from error

    inserted = (
        result.scalar_one_or_none() == record_id
        if returns_inserted_id
        else result.rowcount == 1
    )
    if inserted:
        record = db.get(IdempotencyRecord, record_id)
        if record is None:  # pragma: no cover - defensive driver failure guard
            raise IdempotencyError("idempotency reservation was not persisted")
        return IdempotencyClaim(record, replayed=False)

    existing = db.scalar(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.organization_id == organization_id,
            IdempotencyRecord.key == normalized_key,
        )
        .with_for_update()
    )
    if existing is None:  # pragma: no cover - defensive isolation guard
        raise IdempotencyError("idempotency key could not be resolved")
    _validate_existing(existing, operation, request_hash)
    if existing.response_status == 0:
        raise IdempotencyError("idempotency request is already in progress")
    return IdempotencyClaim(existing, replayed=True)


def complete_idempotency(
    db: Session,
    claim: IdempotencyClaim,
    *,
    resource_id: UUID,
    response_status: int,
    response_body: dict[str, object],
) -> None:
    if claim.replayed:
        raise IdempotencyError("cannot complete a replayed idempotency request")
    if not 100 <= response_status <= 599:
        raise IdempotencyError("invalid idempotency response status")
    claim.record.resource_id = resource_id
    claim.record.response_status = response_status
    claim.record.response_body = response_body
    claim.record.updated_at = datetime.now(UTC)
    db.flush()


def _validate_existing(record: IdempotencyRecord, operation: str, request_hash: str) -> None:
    if record.operation != operation or record.request_hash != request_hash:
        raise IdempotencyError("idempotency key was reused with a different request")


__all__ = [
    "IdempotencyClaim",
    "IdempotencyError",
    "claim_idempotency",
    "complete_idempotency",
    "request_hash",
]
