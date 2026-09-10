from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import Principal
from app.core.idempotency import (
    IdempotencyClaim,
    IdempotencyError,
    claim_idempotency,
    complete_idempotency,
    request_hash,
)
from app.core.pagination import Page
from app.db.models import (
    AuditEvent,
    ChartAccount,
    FiscalPeriod,
    JournalLineRecord,
    Organization,
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
    return request_hash(payload)


def _key(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise AccountingDomainError("a valid idempotency key is required")
    return normalized


def _org(principal: Principal) -> UUID:
    if principal.organization_id is None:
        raise AccountingDomainError("an organization is required for accounting operations")
    return principal.organization_id


def _claim(
    db: Session,
    principal: Principal,
    key: str,
    operation: str,
    request_hash_value: str,
) -> IdempotencyClaim:
    try:
        return claim_idempotency(
            db,
            tenant_id=principal.tenant_id,
            organization_id=principal.organization_id,
            key=key,
            operation=operation,
            request_hash=request_hash_value,
        )
    except IdempotencyError as error:
        raise AccountingDomainError(str(error)) from error


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
        correlation_id=principal.correlation_id or str(uuid4()),
        payload=payload,
    )
    db.add(audit)
    db.flush()
    return audit


def _get_account(
    db: Session, principal: Principal, account_id: UUID, *, for_update: bool = False
) -> ChartAccount:
    statement = select(ChartAccount).where(
        ChartAccount.id == account_id,
        ChartAccount.tenant_id == principal.tenant_id,
        ChartAccount.organization_id == principal.organization_id,
    )
    if for_update:
        statement = statement.with_for_update()
    account = db.scalar(statement)
    if account is None:
        raise AccountingDomainError("account not found")
    return account


def _assert_no_parent_cycle(
    db: Session, principal: Principal, account_id: UUID | None, parent_id: UUID | None
) -> None:
    seen = {account_id} if account_id is not None else set()
    current_id = parent_id
    while current_id is not None:
        if current_id in seen:
            raise AccountingDomainError("account hierarchy cycle is not allowed")
        seen.add(current_id)
        current_id = _get_account(db, principal, current_id).parent_id


def list_accounts(
    db: Session,
    principal: Principal,
    include_inactive: bool = False,
    *,
    limit: int,
    offset: int,
) -> Page[ChartAccount]:
    organization_id = _org(principal)
    statement = select(ChartAccount).where(
        ChartAccount.tenant_id == principal.tenant_id,
        ChartAccount.organization_id == organization_id,
    )
    if not include_inactive:
        statement = statement.where(ChartAccount.is_active.is_(True))
    items = list(
        db.scalars(statement.order_by(ChartAccount.code).offset(offset).limit(limit + 1)).all()
    )
    return Page(items=items[:limit], has_more=len(items) > limit)


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
    claim = _claim(db, principal, key, "account.create", request_hash)
    if claim.replayed:
        if claim.record.resource_id is None:
            raise AccountingDomainError("idempotency record has no account resource")
        return AccountMutationResult(
            _get_account(db, principal, claim.record.resource_id), replayed=True
        )

    code = payload.code.strip().upper()
    if db.scalar(
        select(ChartAccount.id).where(
            ChartAccount.organization_id == organization_id, ChartAccount.code == code
        )
    ):
        raise AccountingDomainError("account code already exists in this organization")
    if payload.parent_id is not None:
        _assert_no_parent_cycle(db, principal, None, payload.parent_id)

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
    try:
        with db.begin_nested():
            db.add(account)
            db.flush()
            _audit(
                db,
                principal,
                "chart_account",
                account.id,
                "account.create",
                {"code": account.code},
            )
            complete_idempotency(
                db,
                claim,
                resource_id=account.id,
                response_status=201,
                response_body={"account_id": str(account.id)},
            )
    except IntegrityError as error:
        db.delete(claim.record)
        db.flush()
        raise AccountingDomainError("account code already exists in this organization") from error
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
    claim = _claim(db, principal, key, "account.update", request_hash)
    if claim.replayed:
        if claim.record.resource_id is None:
            raise AccountingDomainError("idempotency record has no account resource")
        return AccountMutationResult(
            _get_account(db, principal, claim.record.resource_id), replayed=True
        )

    account = _get_account(db, principal, account_id, for_update=True)
    if account.version != payload.expected_version:
        raise AccountingDomainError("account version does not match; reload before updating")
    changes = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if payload.parent_id is not None:
        _assert_no_parent_cycle(db, principal, account.id, payload.parent_id)
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
    complete_idempotency(
        db,
        claim,
        resource_id=account.id,
        response_status=200,
        response_body={"account_id": str(account.id)},
    )
    return AccountMutationResult(account)


def list_periods(
    db: Session, principal: Principal, *, limit: int, offset: int
) -> Page[FiscalPeriod]:
    organization_id = _org(principal)
    items = list(
        db.scalars(
            select(FiscalPeriod)
            .where(
                FiscalPeriod.tenant_id == principal.tenant_id,
                FiscalPeriod.organization_id == organization_id,
            )
            .order_by(FiscalPeriod.start_date.desc())
            .offset(offset)
            .limit(limit + 1)
        ).all()
    )
    return Page(items=items[:limit], has_more=len(items) > limit)


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
    claim = _claim(db, principal, key, "period.create", request_hash)
    if claim.replayed:
        if claim.record.resource_id is None:
            raise AccountingDomainError("idempotency record has no period resource")
        return PeriodMutationResult(
            _get_period(db, principal, claim.record.resource_id), replayed=True
        )
    organization = db.scalar(
        select(Organization)
        .where(
            Organization.id == organization_id,
            Organization.tenant_id == principal.tenant_id,
        )
        .with_for_update()
    )
    if organization is None:
        raise AccountingDomainError("organization not found")
    duplicate = db.scalar(
        select(FiscalPeriod.id).where(
            FiscalPeriod.tenant_id == principal.tenant_id,
            FiscalPeriod.organization_id == organization_id,
            FiscalPeriod.start_date <= payload.end_date,
            FiscalPeriod.end_date >= payload.start_date,
        )
    )
    if duplicate is not None:
        raise AccountingDomainError("fiscal period dates overlap an existing period")
    period = FiscalPeriod(
        tenant_id=principal.tenant_id,
        organization_id=organization_id,
        name=payload.name.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="open",
    )
    try:
        with db.begin_nested():
            db.add(period)
            db.flush()
            _audit(
                db,
                principal,
                "fiscal_period",
                period.id,
                "period.create",
                {"name": period.name},
            )
            complete_idempotency(
                db,
                claim,
                resource_id=period.id,
                response_status=201,
                response_body={"period_id": str(period.id)},
            )
    except IntegrityError as error:
        db.delete(claim.record)
        db.flush()
        raise AccountingDomainError("fiscal period dates overlap an existing period") from error
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
    claim = _claim(db, principal, key, "period.lock", request_hash)
    if claim.replayed:
        if claim.record.resource_id is None:
            raise AccountingDomainError("idempotency record has no period resource")
        return PeriodMutationResult(
            _get_period(db, principal, claim.record.resource_id), replayed=True
        )
    period = db.scalar(
        select(FiscalPeriod)
        .where(
            FiscalPeriod.id == period_id,
            FiscalPeriod.tenant_id == principal.tenant_id,
            FiscalPeriod.organization_id == principal.organization_id,
        )
        .with_for_update()
    )
    if period is None:
        raise AccountingDomainError("fiscal period not found")
    if period.status != "open":
        raise AccountingDomainError("period is already locked")
    period.status = "locked"
    period.locked_at = datetime.now(UTC)
    period.version += 1
    db.flush()
    _audit(db, principal, "fiscal_period", period.id, "period.lock", {"version": period.version})
    complete_idempotency(
        db,
        claim,
        resource_id=period.id,
        response_status=200,
        response_body={"period_id": str(period.id)},
    )
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
