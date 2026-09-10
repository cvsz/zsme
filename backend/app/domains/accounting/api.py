from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.api.dependencies import AccountingReadDep, AccountingWriteDep, SessionDep
from app.core.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_OFFSET,
    MAX_PAGE_SIZE,
    set_page_headers,
)
from app.domains.accounting.schemas import (
    ChartAccountCreate,
    ChartAccountRead,
    ChartAccountUpdate,
    FiscalPeriodCreate,
    FiscalPeriodRead,
)
from app.domains.accounting.service import (
    AccountingDomainError,
    create_account,
    create_period,
    list_accounts,
    list_periods,
    lock_period,
    update_account,
)

router = APIRouter(prefix="/v1/accounting", tags=["accounting-master"])


def _domain_error(error: AccountingDomainError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


def _require_key(value: str | None) -> str:
    if value is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required")
    return value


def _account_response(account, response_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=response_status,
        content=jsonable_encoder(ChartAccountRead.model_validate(account)),
    )


def _period_response(period, response_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=response_status,
        content=jsonable_encoder(FiscalPeriodRead.model_validate(period)),
    )


@router.get("/accounts", response_model=list[ChartAccountRead])
def get_accounts(
    principal: AccountingReadDep,
    db: SessionDep,
    response: Response,
    include_inactive: bool = False,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0, le=MAX_PAGE_OFFSET),
) -> list[ChartAccountRead]:
    page = list_accounts(
        db, principal, include_inactive=include_inactive, limit=limit, offset=offset
    )
    set_page_headers(response, limit=limit, offset=offset, has_more=page.has_more)
    return page.items


@router.post("/accounts", response_model=ChartAccountRead, status_code=status.HTTP_201_CREATED)
def post_account(
    payload: ChartAccountCreate,
    principal: AccountingWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = create_account(db, payload, principal, _require_key(idempotency_key))
    except AccountingDomainError as error:
        raise _domain_error(error) from error
    return _account_response(result.account, 200 if result.replayed else 201)


@router.patch("/accounts/{account_id}", response_model=ChartAccountRead)
def patch_account(
    account_id: UUID,
    payload: ChartAccountUpdate,
    principal: AccountingWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = update_account(db, account_id, payload, principal, _require_key(idempotency_key))
    except AccountingDomainError as error:
        raise _domain_error(error) from error
    return _account_response(result.account, 200)


@router.get("/periods", response_model=list[FiscalPeriodRead])
def get_periods(
    principal: AccountingReadDep,
    db: SessionDep,
    response: Response,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0, le=MAX_PAGE_OFFSET),
) -> list[FiscalPeriodRead]:
    page = list_periods(db, principal, limit=limit, offset=offset)
    set_page_headers(response, limit=limit, offset=offset, has_more=page.has_more)
    return page.items


@router.post("/periods", response_model=FiscalPeriodRead, status_code=status.HTTP_201_CREATED)
def post_period(
    payload: FiscalPeriodCreate,
    principal: AccountingWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = create_period(db, payload, principal, _require_key(idempotency_key))
    except AccountingDomainError as error:
        raise _domain_error(error) from error
    return _period_response(result.period, 200 if result.replayed else 201)


@router.post("/periods/{period_id}/lock", response_model=FiscalPeriodRead)
def post_period_lock(
    period_id: UUID,
    principal: AccountingWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = lock_period(db, period_id, principal, _require_key(idempotency_key))
    except AccountingDomainError as error:
        raise _domain_error(error) from error
    return _period_response(result.period, 200)


__all__ = ["router"]
