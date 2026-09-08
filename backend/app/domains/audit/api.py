from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.exceptions import HTTPException

from app.api.dependencies import AuditReadDep, SessionDep
from app.domains.audit.schemas import AuditEventPage
from app.domains.audit.service import AuditDomainError, list_events

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("/events", response_model=AuditEventPage)
def get_events(
    principal: AuditReadDep,
    db: SessionDep,
    action: Annotated[str | None, Query(max_length=120)] = None,
    entity_type: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> AuditEventPage:
    try:
        return list_events(
            db,
            principal,
            action=action,
            entity_type=entity_type,
            limit=limit,
            offset=offset,
        )
    except AuditDomainError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


__all__ = ["router"]
