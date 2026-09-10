from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import or_, select
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
from app.db.models import AuditEvent, BusinessPartner, IdempotencyRecord
from app.domains.partners.schemas import PartnerCreate, PartnerUpdate


class PartnerDomainError(Exception):
    """A safe, expected partner-domain failure."""


@dataclass(frozen=True)
class PartnerMutationResult:
    partner: BusinessPartner
    replayed: bool = False


def _request_hash(payload: object) -> str:
    return request_hash(payload)


def _validate_key(idempotency_key: str) -> str:
    normalized_key = idempotency_key.strip()
    if not normalized_key or len(normalized_key) > 200:
        raise PartnerDomainError("a valid idempotency key is required")
    return normalized_key


def _existing_partner_result(
    db: Session,
    principal: Principal,
    record: IdempotencyRecord,
    request_hash: str,
    operation: str,
) -> PartnerMutationResult:
    if record.operation != operation or record.request_hash != request_hash:
        raise PartnerDomainError("idempotency key was reused with a different request")
    if record.resource_id is None:
        raise PartnerDomainError("idempotency record has no partner resource")
    partner = db.scalar(
        select(BusinessPartner).where(
            BusinessPartner.id == record.resource_id,
            BusinessPartner.tenant_id == principal.tenant_id,
            BusinessPartner.organization_id == principal.organization_id,
        )
    )
    if partner is None:
        raise PartnerDomainError("idempotency record points to a missing partner")
    return PartnerMutationResult(partner=partner, replayed=True)


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
        raise PartnerDomainError(str(error)) from error


def _require_organization(principal: Principal) -> UUID:
    if principal.organization_id is None:
        raise PartnerDomainError("an organization is required for partner operations")
    return principal.organization_id


def _clean(value: str | None) -> str | None:
    return value.strip() if value is not None else None


def _create_audit(
    db: Session,
    principal: Principal,
    partner: BusinessPartner,
    action: str,
    payload: dict[str, object],
) -> AuditEvent:
    audit = AuditEvent(
        tenant_id=principal.tenant_id,
        organization_id=principal.organization_id,
        actor_user_id=principal.user_id,
        action=action,
        entity_type="business_partner",
        entity_id=partner.id,
        correlation_id=principal.correlation_id or str(uuid4()),
        payload=payload,
    )
    db.add(audit)
    db.flush()
    return audit


def create_partner(
    db: Session,
    payload: PartnerCreate,
    principal: Principal,
    idempotency_key: str,
) -> PartnerMutationResult:
    organization_id = _require_organization(principal)
    key = _validate_key(idempotency_key)
    request_hash = _request_hash(payload.model_dump(mode="json"))
    claim = _claim(db, principal, key, "partner.create", request_hash)
    if claim.replayed:
        return _existing_partner_result(db, principal, claim.record, request_hash, "partner.create")

    partner = BusinessPartner(
        tenant_id=principal.tenant_id,
        organization_id=organization_id,
        partner_code=payload.partner_code.strip().upper(),
        partner_type=payload.partner_type,
        display_name=payload.display_name.strip(),
        legal_name=_clean(payload.legal_name),
        tax_id=_clean(payload.tax_id),
        tax_branch=payload.tax_branch.strip(),
        email=_clean(payload.email.lower() if payload.email else None),
        phone=_clean(payload.phone),
        payment_terms_days=payload.payment_terms_days,
        credit_limit=payload.credit_limit,
        tags=[tag.strip() for tag in payload.tags if tag.strip()],
    )
    try:
        with db.begin_nested():
            db.add(partner)
            db.flush()
            _create_audit(
                db,
                principal,
                partner,
                "partner.create",
                {"partner_code": partner.partner_code, "partner_type": partner.partner_type},
            )
            complete_idempotency(
                db,
                claim,
                resource_id=partner.id,
                response_status=201,
                response_body={"partner_id": str(partner.id)},
            )
    except IntegrityError as error:
        db.delete(claim.record)
        db.flush()
        raise PartnerDomainError("partner code already exists in this organization") from error
    return PartnerMutationResult(partner=partner)


def list_partners(
    db: Session,
    principal: Principal,
    *,
    partner_type: str | None = None,
    search: str | None = None,
    include_archived: bool = False,
    limit: int,
    offset: int,
) -> Page[BusinessPartner]:
    organization_id = _require_organization(principal)
    statement = select(BusinessPartner).where(
        BusinessPartner.tenant_id == principal.tenant_id,
        BusinessPartner.organization_id == organization_id,
    )
    if not include_archived:
        statement = statement.where(BusinessPartner.is_active.is_(True))
    if partner_type is not None:
        statement = statement.where(BusinessPartner.partner_type.in_([partner_type, "both"]))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                BusinessPartner.partner_code.ilike(pattern),
                BusinessPartner.display_name.ilike(pattern),
                BusinessPartner.legal_name.ilike(pattern),
                BusinessPartner.tax_id.ilike(pattern),
            )
        )
    items = list(
        db.scalars(
            statement.order_by(BusinessPartner.partner_code).offset(offset).limit(limit + 1)
        ).all()
    )
    return Page(items=items[:limit], has_more=len(items) > limit)


def get_partner(
    db: Session, partner_id: UUID, principal: Principal, *, for_update: bool = False
) -> BusinessPartner:
    organization_id = _require_organization(principal)
    statement = select(BusinessPartner).where(
        BusinessPartner.id == partner_id,
        BusinessPartner.tenant_id == principal.tenant_id,
        BusinessPartner.organization_id == organization_id,
    )
    if for_update:
        statement = statement.with_for_update()
    partner = db.scalar(statement)
    if partner is None:
        raise PartnerDomainError("partner not found")
    return partner


def update_partner(
    db: Session,
    partner_id: UUID,
    payload: PartnerUpdate,
    principal: Principal,
    idempotency_key: str,
) -> PartnerMutationResult:
    _require_organization(principal)
    key = _validate_key(idempotency_key)
    request_hash = _request_hash(
        {"partner_id": str(partner_id), "payload": payload.model_dump(mode="json")}
    )
    claim = _claim(db, principal, key, "partner.update", request_hash)
    if claim.replayed:
        return _existing_partner_result(db, principal, claim.record, request_hash, "partner.update")

    partner = get_partner(db, partner_id, principal, for_update=True)
    if partner.version != payload.expected_version:
        raise PartnerDomainError("partner version does not match; reload before updating")
    changes = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    for field, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        if field == "email" and value:
            value = value.lower()
        if field == "tags" and value is not None:
            value = [tag.strip() for tag in value if tag.strip()]
        setattr(partner, field, value)
    partner.version += 1
    db.flush()
    _create_audit(db, principal, partner, "partner.update", {"version": partner.version})
    complete_idempotency(
        db,
        claim,
        resource_id=partner.id,
        response_status=200,
        response_body={"partner_id": str(partner.id)},
    )
    return PartnerMutationResult(partner=partner)


def archive_partner(
    db: Session,
    partner_id: UUID,
    expected_version: int,
    principal: Principal,
    idempotency_key: str,
) -> PartnerMutationResult:
    _require_organization(principal)
    key = _validate_key(idempotency_key)
    request_payload = {"partner_id": str(partner_id), "expected_version": expected_version}
    request_hash = _request_hash(request_payload)
    claim = _claim(db, principal, key, "partner.archive", request_hash)
    if claim.replayed:
        return _existing_partner_result(
            db, principal, claim.record, request_hash, "partner.archive"
        )

    partner = get_partner(db, partner_id, principal, for_update=True)
    if partner.version != expected_version:
        raise PartnerDomainError("partner version does not match; reload before archiving")
    if not partner.is_active:
        raise PartnerDomainError("partner is already archived")
    partner.is_active = False
    partner.version += 1
    partner.updated_at = datetime.now(UTC)
    db.flush()
    _create_audit(db, principal, partner, "partner.archive", {"version": partner.version})
    complete_idempotency(
        db,
        claim,
        resource_id=partner.id,
        response_status=200,
        response_body={"partner_id": str(partner.id)},
    )
    return PartnerMutationResult(partner=partner)


__all__ = [
    "PartnerDomainError",
    "PartnerMutationResult",
    "archive_partner",
    "create_partner",
    "get_partner",
    "list_partners",
    "update_partner",
]
