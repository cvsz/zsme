from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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
from app.db.models import AuditEvent, Organization, TaxRateRule
from app.domains.tax.schemas import TaxRateCreate, TaxType


class TaxDomainError(Exception):
    """A safe, expected tax-rule domain failure."""


@dataclass(frozen=True)
class TaxRateMutationResult:
    rule: TaxRateRule
    replayed: bool = False


def _hash(payload: object) -> str:
    return request_hash(payload)


def _key(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise TaxDomainError("a valid idempotency key is required")
    return normalized


def _org(principal: Principal) -> UUID:
    if principal.organization_id is None:
        raise TaxDomainError("an organization is required for tax operations")
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
        raise TaxDomainError(str(error)) from error


def _get_rule(db: Session, principal: Principal, rule_id: UUID) -> TaxRateRule:
    rule = db.scalar(
        select(TaxRateRule).where(
            TaxRateRule.id == rule_id,
            TaxRateRule.tenant_id == principal.tenant_id,
            TaxRateRule.organization_id == principal.organization_id,
        )
    )
    if rule is None:
        raise TaxDomainError("tax rate rule not found")
    return rule


def _audit(db: Session, principal: Principal, rule: TaxRateRule) -> AuditEvent:
    audit = AuditEvent(
        tenant_id=principal.tenant_id,
        organization_id=principal.organization_id,
        actor_user_id=principal.user_id,
        action="tax_rate.create",
        entity_type="tax_rate_rule",
        entity_id=rule.id,
        correlation_id=principal.correlation_id or str(uuid4()),
        payload={
            "tax_type": rule.tax_type,
            "code": rule.code,
            "rate": str(rule.rate),
            "effective_from": rule.effective_from.isoformat(),
            "effective_to": rule.effective_to.isoformat() if rule.effective_to else None,
        },
    )
    db.add(audit)
    db.flush()
    return audit


def _overlaps(left: TaxRateRule, right: TaxRateCreate) -> bool:
    left_end = left.effective_to or date.max
    right_end = right.effective_to or date.max
    return left.effective_from <= right_end and right.effective_from <= left_end


def create_rate(
    db: Session,
    payload: TaxRateCreate,
    principal: Principal,
    idempotency_key: str,
) -> TaxRateMutationResult:
    organization_id = _org(principal)
    key = _key(idempotency_key)
    normalized_payload = payload.model_dump(mode="json")
    request_hash = _hash({"operation": "tax_rate.create", "payload": normalized_payload})
    claim = _claim(db, principal, key, "tax_rate.create", request_hash)
    if claim.replayed:
        if claim.record.resource_id is None:
            raise TaxDomainError("idempotency record has no tax rate resource")
        return TaxRateMutationResult(
            _get_rule(db, principal, claim.record.resource_id), replayed=True
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
        raise TaxDomainError("organization not found")

    rules = list(
        db.scalars(
            select(TaxRateRule)
            .where(
                TaxRateRule.tenant_id == principal.tenant_id,
                TaxRateRule.organization_id == organization_id,
                TaxRateRule.tax_type == payload.tax_type,
                TaxRateRule.code == payload.code.strip().upper(),
                TaxRateRule.is_active.is_(True),
            )
            .with_for_update()
        ).all()
    )
    if any(_overlaps(rule, payload) for rule in rules):
        raise TaxDomainError("tax rate effective dates overlap an existing rule")
    rule = TaxRateRule(
        tenant_id=principal.tenant_id,
        organization_id=organization_id,
        tax_type=payload.tax_type,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        rate=payload.rate,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        is_active=True,
    )
    try:
        with db.begin_nested():
            db.add(rule)
            db.flush()
            _audit(db, principal, rule)
            complete_idempotency(
                db,
                claim,
                resource_id=rule.id,
                response_status=201,
                response_body={"tax_rate_id": str(rule.id)},
            )
    except IntegrityError as error:
        db.delete(claim.record)
        db.flush()
        raise TaxDomainError("tax rate rule already exists") from error
    return TaxRateMutationResult(rule)


def list_rates(
    db: Session,
    principal: Principal,
    tax_type: TaxType | None = None,
    *,
    limit: int,
    offset: int,
) -> Page[TaxRateRule]:
    organization_id = _org(principal)
    statement = select(TaxRateRule).where(
        TaxRateRule.tenant_id == principal.tenant_id,
        TaxRateRule.organization_id == organization_id,
        TaxRateRule.is_active.is_(True),
    )
    if tax_type is not None:
        statement = statement.where(TaxRateRule.tax_type == tax_type)
    items = list(
        db.scalars(
            statement.order_by(
                TaxRateRule.tax_type, TaxRateRule.code, TaxRateRule.effective_from.desc()
            )
            .offset(offset)
            .limit(limit + 1)
        ).all()
    )
    return Page(items=items[:limit], has_more=len(items) > limit)


def effective_rate(
    db: Session, principal: Principal, tax_type: TaxType, code: str, on_date: date
) -> TaxRateRule:
    organization_id = _org(principal)
    rule = db.scalar(
        select(TaxRateRule)
        .where(
            TaxRateRule.tenant_id == principal.tenant_id,
            TaxRateRule.organization_id == organization_id,
            TaxRateRule.tax_type == tax_type,
            TaxRateRule.code == code.strip().upper(),
            TaxRateRule.effective_from <= on_date,
            (TaxRateRule.effective_to.is_(None) | (TaxRateRule.effective_to >= on_date)),
            TaxRateRule.is_active.is_(True),
        )
        .order_by(TaxRateRule.effective_from.desc())
    )
    if rule is None:
        raise TaxDomainError("no effective tax rate rule found")
    return rule


__all__ = ["TaxDomainError", "TaxRateMutationResult", "create_rate", "effective_rate", "list_rates"]
