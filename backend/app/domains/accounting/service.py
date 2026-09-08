from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import Principal
from app.db.models import (
    AuditEvent,
    ChartAccount,
    FiscalPeriod,
    IdempotencyRecord,
    JournalLineRecord,
)
from app.domains.accounting.schemas import (
    ChartAccountCreate,
    ChartAccountUpdate,
    FiscalPeriodCreate,
)


class AccountingDomainError(Exception):
    """A safe, expected accounting-master domain failure."""


@dataclass(frozen=True)
class AccountMutationResult:
    account: ChartAccount
    replayed: bool = False


@dataclass(frozen=True)
class PeriodMutationResult:
    period: FiscalPeriod
    replayed: bool = False


def _hash(payload: object) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


def _key(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise AccountingDomainError("a valid idempotency key is required")
    return normalized


def _org(principal: Principal) -> UUID:
    if principal.organization_id is None:
        raise AccountingDomainError("an organization is required for accounting operations")
    return principal.organization_id


def _record(db: Session, principal: Principal, key: str) -> IdempotencyRecord | None:
    return db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == principal.tenant_id,
            IdempotencyRecord.organization_id == principal.organization_id,
            IdempotencyRecord.key == key,
        )
    )


def _audit(
    db: Session,
    principal: Principal,
    entity_type: str,
    entity_id: UUID,
    action: str,
    payload: dict[str, object],
) -> AuditEvent:
    audit = AuditEvent(
        tenant_id=principal.tenant_id,
        organization_id=principal.organization_id,
        actor_user_id=principal.user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        correlation_id=str(uuid4()),
        payload=payload,
    )
    db.add(audit)
    db.flush()
    return audit


def _store(
    db: Session,
    principal: Principal,
    key: str,
    operation: str,
    request_hash: str,
    resource_id: UUID,
    response_status: int,
    body_key: str,
) -> None:
    db.add(
        IdempotencyRecord(
            tenant_id=principal.tenant_id,
            organization_id=principal.organization_id,
            key=key,
            operation=operation,
            request_hash=request_hash,
            response_status=response_status,
            response_body={body_key: str(resource_id)},
            resource_id=resource_id,
        )
    )
    db.flush()


def _get_account(db: Session, principal: Principal, account_id: UUID) -> ChartAccount:
    account = db.scalar(
        select(ChartAccount).where(
            ChartAccount.id == account_id,
            ChartAccount.tenant_id == principal.tenant_id,
            ChartAccount.organization_id == principal.organization_id,
        )
    )
    if account is None:
        raise AccountingDomainError("account not found")
    return account


def list_accounts(
    db: Session, principal: Principal, include_inactive: bool = False
) -> list[ChartAccount]:
    organization_id = _org(principal)
    statement = select(ChartAccount).where(
        ChartAccount.tenant_id == principal.tenant_id,
        ChartAccount.organization_id == organization_id,
    )
    if not include_inactive:
        statement = statement.where(ChartAccount.is_active.is_(True))
    return list(db.scalars(statement.order_by(ChartAccount.code)).all())


def create_account(
    db: Session,
    payload: ChartAccountCreate,
    principal: Principal,
    idempotency_key: str,
) -> AccountMutationResult:
    organization_id = _org(principal)
    key = _key(idempotency_key)
    request_hash = _hash(
        {"operation": "account.create", "payload": payload.model_dump(mode="json")}
    )
    existing = _record(db, principal, key)
    if existing is not None:
        if existing.operation != "account.create" or existing.request_hash != request_hash:
            raise AccountingDomainError("idempotency key was reused with a different request")
        if existing.resource_id is None:
            raise AccountingDomainError("idempotency record has no account resource")
        return AccountMutationResult(
            _get_account(db, principal, existing.resource_id), replayed=True
        )

    code = payload.code.strip().upper()
    if db.scalar(
        select(ChartAccount.id).where(
            ChartAccount.organization_id == organization_id, ChartAccount.code == code
        )
    ):
        raise AccountingDomainError("account code already exists in this organization")
    if payload.parent_id is not None:
        parent = _get_account(db, principal, payload.parent_id)
        if parent.id == payload.parent_id and parent.parent_id == payload.parent_id:
            raise AccountingDomainError("an account cannot be its own parent")

    account = ChartAccount(
        tenant_id=principal.tenant_id,
        organization_id=organization_id,
        code=code,
        name=payload.name.strip(),
        account_type=payload.account_type,
        parent_id=payload.parent_id,
        is_control=payload.is_control,
        is_active=True,
    )
    db.add(account)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise AccountingDomainError("account code already exists in this organization") from error
    _audit(db, principal, "chart_account", account.id, "account.create", {"code": account.code})
    _store(db, principal, key, "account.create", request_hash, account.id, 201, "account_id")
    return AccountMutationResult(account)


def update_account(
    db: Session,
    account_id: UUID,
    payload: ChartAccountUpdate,
    principal: Principal,
    idempotency_key: str,
) -> AccountMutationResult:
    _org(principal)
    key = _key(idempotency_key)
    request_hash = _hash(
        {
            "operation": "account.update",
            "account_id": str(account_id),
            "payload": payload.model_dump(mode="json"),
        }
    )
    existing = _record(db, principal, key)
    if existing is not None:
        if existing.operation != "account.update" or existing.request_hash != request_hash:
            raise AccountingDomainError("idempotency key was reused with a different request")
        if existing.resource_id is None:
            raise AccountingDomainError("idempotency record has no account resource")
        return AccountMutationResult(
            _get_account(db, principal, existing.resource_id), replayed=True
        )

    account = _get_account(db, principal, account_id)
    if account.version != payload.expected_version:
        raise AccountingDomainError("account version does not match; reload before updating")
    changes = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if payload.parent_id is not None:
        parent = _get_account(db, principal, payload.parent_id)
        if parent.id == account.id:
            raise AccountingDomainError("an account cannot be its own parent")
        if parent.id == account.id or parent.parent_id == account.id:
            raise AccountingDomainError("account hierarchy cycle is not allowed")
    has_postings = db.scalar(
        select(JournalLineRecord.id).where(JournalLineRecord.account_id == account.id)
    )
    if has_postings is not None and any(field in changes for field in ("parent_id", "is_control")):
        raise AccountingDomainError("posted account structure cannot be changed")
    if "name" in changes:
        account.name = str(changes["name"]).strip()
    for field in ("parent_id", "is_control", "is_active"):
        if field in changes:
            setattr(account, field, changes[field])
    account.version += 1
    db.flush()
    _audit(
        db, principal, "chart_account", account.id, "account.update", {"version": account.version}
    )
    _store(db, principal, key, "account.update", request_hash, account.id, 200, "account_id")
    return AccountMutationResult(account)


def list_periods(db: Session, principal: Principal) -> list[FiscalPeriod]:
    organization_id = _org(principal)
    return list(
        db.scalars(
            select(FiscalPeriod)
            .where(
                FiscalPeriod.tenant_id == principal.tenant_id,
                FiscalPeriod.organization_id == organization_id,
            )
            .order_by(FiscalPeriod.start_date.desc())
        ).all()
    )


def _get_period(db: Session, principal: Principal, period_id: UUID) -> FiscalPeriod:
    period = db.scalar(
        select(FiscalPeriod).where(
            FiscalPeriod.id == period_id,
            FiscalPeriod.tenant_id == principal.tenant_id,
            FiscalPeriod.organization_id == principal.organization_id,
        )
    )
    if period is None:
        raise AccountingDomainError("fiscal period not found")
    return period


def create_period(
    db: Session,
    payload: FiscalPeriodCreate,
    principal: Principal,
    idempotency_key: str,
) -> PeriodMutationResult:
    organization_id = _org(principal)
    key = _key(idempotency_key)
    request_hash = _hash({"operation": "period.create", "payload": payload.model_dump(mode="json")})
    existing = _record(db, principal, key)
    if existing is not None:
        if existing.operation != "period.create" or existing.request_hash != request_hash:
            raise AccountingDomainError("idempotency key was reused with a different request")
        if existing.resource_id is None:
            raise AccountingDomainError("idempotency record has no period resource")
        return PeriodMutationResult(_get_period(db, principal, existing.resource_id), replayed=True)
    duplicate = db.scalar(
        select(FiscalPeriod.id).where(
            FiscalPeriod.organization_id == organization_id,
            FiscalPeriod.start_date == payload.start_date,
            FiscalPeriod.end_date == payload.end_date,
        )
    )
    if duplicate is not None:
        raise AccountingDomainError("fiscal period dates already exist in this organization")
    period = FiscalPeriod(
        tenant_id=principal.tenant_id,
        organization_id=organization_id,
        name=payload.name.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="open",
    )
    db.add(period)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise AccountingDomainError(
            "fiscal period dates already exist in this organization"
        ) from error
    _audit(db, principal, "fiscal_period", period.id, "period.create", {"name": period.name})
    _store(db, principal, key, "period.create", request_hash, period.id, 201, "period_id")
    return PeriodMutationResult(period)


def lock_period(
    db: Session,
    period_id: UUID,
    principal: Principal,
    idempotency_key: str,
) -> PeriodMutationResult:
    _org(principal)
    key = _key(idempotency_key)
    request_hash = _hash({"operation": "period.lock", "period_id": str(period_id)})
    existing = _record(db, principal, key)
    if existing is not None:
        if existing.operation != "period.lock" or existing.request_hash != request_hash:
            raise AccountingDomainError("idempotency key was reused with a different request")
        if existing.resource_id is None:
            raise AccountingDomainError("idempotency record has no period resource")
        return PeriodMutationResult(_get_period(db, principal, existing.resource_id), replayed=True)
    period = _get_period(db, principal, period_id)
    if period.status != "open":
        raise AccountingDomainError("period is already locked")
    period.status = "locked"
    period.locked_at = datetime.now(UTC)
    period.version += 1
    db.flush()
    _audit(db, principal, "fiscal_period", period.id, "period.lock", {"version": period.version})
    _store(db, principal, key, "period.lock", request_hash, period.id, 200, "period_id")
    return PeriodMutationResult(period)


__all__ = [
    "AccountMutationResult",
    "AccountingDomainError",
    "PeriodMutationResult",
    "create_account",
    "create_period",
    "list_accounts",
    "list_periods",
    "lock_period",
    "update_account",
]
