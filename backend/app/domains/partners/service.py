from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import Principal
from app.db.models import AuditEvent, BusinessPartner, IdempotencyRecord
from app.domains.partners.schemas import PartnerCreate, PartnerUpdate


class PartnerDomainError(Exception):
    """A safe, expected partner-domain failure."""


@dataclass(frozen=True)
class PartnerMutationResult:
    partner: BusinessPartner
    replayed: bool = False


def _request_hash(payload: object) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


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


def _find_idempotency_record(
    db: Session, principal: Principal, key: str, request_hash: str, operation: str
) -> PartnerMutationResult | None:
    record = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == principal.tenant_id,
            IdempotencyRecord.organization_id == principal.organization_id,
            IdempotencyRecord.key == key,
        )
    )
    if record is None:
        return None
    return _existing_partner_result(db, principal, record, request_hash, operation)


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
        correlation_id=str(uuid4()),
        payload=payload,
    )
    db.add(audit)
    db.flush()
    return audit


def _store_idempotency(
    db: Session,
    principal: Principal,
    key: str,
    operation: str,
    request_hash: str,
    partner: BusinessPartner,
) -> None:
    db.add(
        IdempotencyRecord(
            tenant_id=principal.tenant_id,
            organization_id=principal.organization_id,
            key=key,
            operation=operation,
            request_hash=request_hash,
            response_status=201,
            response_body={"partner_id": str(partner.id)},
            resource_id=partner.id,
        )
    )
    db.flush()


def create_partner(
    db: Session,
    payload: PartnerCreate,
    principal: Principal,
    idempotency_key: str,
) -> PartnerMutationResult:
    organization_id = _require_organization(principal)
    key = _validate_key(idempotency_key)
    request_hash = _request_hash(payload.model_dump(mode="json"))
    existing = _find_idempotency_record(db, principal, key, request_hash, "partner.create")
    if existing is not None:
        return existing

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
    db.add(partner)
    try:
        db.flush()
        _create_audit(
            db,
            principal,
            partner,
            "partner.create",
            {"partner_code": partner.partner_code, "partner_type": partner.partner_type},
        )
        _store_idempotency(db, principal, key, "partner.create", request_hash, partner)
    except IntegrityError as error:
        db.rollback()
        existing = _find_idempotency_record(db, principal, key, request_hash, "partner.create")
        if existing is not None:
            return existing
        raise PartnerDomainError("partner code already exists in this organization") from error
    return PartnerMutationResult(partner=partner)


def list_partners(
    db: Session,
    principal: Principal,
    *,
    partner_type: str | None = None,
    search: str | None = None,
    include_archived: bool = False,
) -> list[BusinessPartner]:
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
    return list(db.scalars(statement.order_by(BusinessPartner.partner_code)).all())


def get_partner(db: Session, partner_id: UUID, principal: Principal) -> BusinessPartner:
    organization_id = _require_organization(principal)
    partner = db.scalar(
        select(BusinessPartner).where(
            BusinessPartner.id == partner_id,
            BusinessPartner.tenant_id == principal.tenant_id,
            BusinessPartner.organization_id == organization_id,
        )
    )
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
    request_hash = _request_hash(payload.model_dump(mode="json"))
    existing = _find_idempotency_record(db, principal, key, request_hash, "partner.update")
    if existing is not None:
        return existing

    partner = get_partner(db, partner_id, principal)
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
    _store_idempotency(db, principal, key, "partner.update", request_hash, partner)
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
    existing = _find_idempotency_record(db, principal, key, request_hash, "partner.archive")
    if existing is not None:
        return existing

    partner = get_partner(db, partner_id, principal)
    if partner.version != expected_version:
        raise PartnerDomainError("partner version does not match; reload before archiving")
    if not partner.is_active:
        raise PartnerDomainError("partner is already archived")
    partner.is_active = False
    partner.version += 1
    partner.updated_at = datetime.now(UTC)
    db.flush()
    _create_audit(db, principal, partner, "partner.archive", {"version": partner.version})
    _store_idempotency(db, principal, key, "partner.archive", request_hash, partner)
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
