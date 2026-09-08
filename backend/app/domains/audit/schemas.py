from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    organization_id: UUID | None
    actor_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    correlation_id: str
    payload: dict[str, Any]
    created_at: datetime


class AuditEventPage(BaseModel):
    items: list[AuditEventRead] = Field(default_factory=list)
    limit: int
    offset: int
    total: int
    next_offset: int | None


__all__ = ["AuditEventPage", "AuditEventRead"]
