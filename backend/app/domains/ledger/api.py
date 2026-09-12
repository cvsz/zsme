from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.api.dependencies import AccountingReadDep, AccountingWriteDep, SessionDep
from app.domains.ledger.schemas import JournalEntryPage, JournalPostCommand, JournalPostResult
from app.domains.ledger.service import (
    DomainError,
    list_journal_entries,
    post_journal_entry,
    reverse_journal_entry,
)

router = APIRouter(prefix="/v1/accounting", tags=["accounting"])


def _domain_error(error: DomainError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.get("/journal-entries", response_model=JournalEntryPage)
def get_journal_entries(
    principal: AccountingReadDep,
    db: SessionDep,
    reference: Annotated[str | None, Query(max_length=100)] = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> JournalEntryPage:
    try:
        return list_journal_entries(
            db,
            principal,
            reference=reference,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
    except DomainError as error:
        raise _domain_error(error) from error


@router.post("/journal-entries", response_model=JournalPostResult, status_code=201)
def post_entry(
    command: JournalPostCommand,
    principal: AccountingWriteDep,
    db: SessionDep,
    reversal_date: date | None = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required")
    try:
        result = post_journal_entry(db, command, principal, idempotency_key)
    except DomainError as error:
        raise _domain_error(error) from error
    response_status = 201 if result.status == "posted" else 200
    return JSONResponse(status_code=response_status, content=jsonable_encoder(result))


@router.post(
    "/journal-entries/{entry_id}/reverse",
    response_model=JournalPostResult,
    status_code=201,
)
def reverse_entry(
    entry_id: UUID,
    principal: AccountingWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required")
    try:
        result = reverse_journal_entry(
            db, entry_id, principal, idempotency_key, reversal_date=reversal_date
        )
    except DomainError as error:
        raise _domain_error(error) from error
    response_status = 201 if result.status == "posted" else 200
    return JSONResponse(status_code=response_status, content=jsonable_encoder(result))


__all__ = ["router"]
