from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import Principal
from app.db.models import AuditEvent
from app.domains.audit.schemas import AuditEventPage, AuditEventRead


class AuditDomainError(Exception):
    """A safe, expected audit-domain failure."""


_SENSITIVE_KEY_PARTS = (
    "password",
    "token",
    "secret",
    "credential",
    "authorization",
    "private_key",
    "privatekey",
    "api_key",
    "apikey",
)


def _is_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def redact_payload(value: Any, *, key: str | None = None) -> Any:
    if key is not None and _is_sensitive(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_payload(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, tuple):
        return [redact_payload(item) for item in value]
    return value


def _organization_id(principal: Principal):
    if principal.organization_id is None:
        raise AuditDomainError("an organization is required for audit operations")
    return principal.organization_id


def list_events(
    db: Session,
    principal: Principal,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AuditEventPage:
    organization_id = _organization_id(principal)
    filters = [
        AuditEvent.tenant_id == principal.tenant_id,
        AuditEvent.organization_id == organization_id,
    ]
    if action and action.strip():
        filters.append(AuditEvent.action == action.strip())
    if entity_type and entity_type.strip():
        filters.append(AuditEvent.entity_type == entity_type.strip())

    total = db.scalar(select(func.count(AuditEvent.id)).where(*filters)) or 0
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(*filters)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    items = [
        AuditEventRead(
            id=event.id,
            tenant_id=event.tenant_id,
            organization_id=event.organization_id,
            actor_user_id=event.actor_user_id,
            action=event.action,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            correlation_id=event.correlation_id,
            payload=redact_payload(event.payload),
            created_at=event.created_at,
        )
        for event in events
    ]
    next_offset = offset + len(items) if offset + len(items) < total else None
    return AuditEventPage(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
        next_offset=next_offset,
    )


__all__ = ["AuditDomainError", "list_events", "redact_payload"]
