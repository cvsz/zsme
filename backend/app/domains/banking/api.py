from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.api.dependencies import BankingReadDep, BankingWriteDep, SessionDep
from app.core.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_OFFSET,
    MAX_PAGE_SIZE,
    set_page_headers,
)
from app.domains.banking.schemas import (
    BankAccountCreate,
    BankAccountRead,
    BankImportCreate,
    BankImportRead,
    BankReconcileRequest,
    BankTransactionRead,
    BankTransactionStatus,
)
from app.domains.banking.service import (
    BankingDomainError,
    create_account,
    import_transactions,
    list_accounts,
    list_transactions,
    reconcile_transaction,
)
from app.domains.banking.service import (
    get_account as get_bank_account,
)
from app.domains.banking.service import (
    get_transaction as get_bank_transaction,
)

router = APIRouter(prefix="/v1/banking", tags=["banking"])


def _error(error: BankingDomainError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


def _key(value: str | None) -> str:
    if value is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required")
    return value


@router.get("/accounts", response_model=list[BankAccountRead])
def get_accounts(
    principal: BankingReadDep,
    db: SessionDep,
    response: Response,
    include_inactive: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
) -> list[BankAccountRead]:
    page = list_accounts(
        db,
        principal,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )
    set_page_headers(response, limit=limit, offset=offset, has_more=page.has_more)
    return page.items


@router.post("/accounts", response_model=BankAccountRead, status_code=status.HTTP_201_CREATED)
def post_account(
    payload: BankAccountCreate,
    principal: BankingWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = create_account(db, payload, principal, _key(idempotency_key))
    except BankingDomainError as error:
        raise _error(error) from error
    return JSONResponse(
        status_code=200 if result.replayed else 201,
        content=jsonable_encoder(BankAccountRead.model_validate(result.account)),
    )


@router.get("/accounts/{account_id}", response_model=BankAccountRead)
def get_account(account_id: UUID, principal: BankingReadDep, db: SessionDep) -> BankAccountRead:
    try:
        return get_bank_account(db, principal, account_id)
    except BankingDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/accounts/{account_id}/imports",
    response_model=BankImportRead,
    status_code=status.HTTP_201_CREATED,
)
def post_import(
    account_id: UUID,
    payload: BankImportCreate,
    principal: BankingWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = import_transactions(db, account_id, payload, principal, _key(idempotency_key))
    except BankingDomainError as error:
        raise _error(error) from error
    return JSONResponse(
        status_code=200 if result.replayed else 201,
        content=jsonable_encoder(BankImportRead.model_validate(result.batch)),
    )


@router.get("/transactions", response_model=list[BankTransactionRead])
def get_transactions(
    principal: BankingReadDep,
    db: SessionDep,
    response: Response,
    account_id: Annotated[UUID | None, Query()] = None,
    transaction_status: Annotated[BankTransactionStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
) -> list[BankTransactionRead]:
    page = list_transactions(
        db,
        principal,
        account_id,
        transaction_status,
        limit=limit,
        offset=offset,
    )
    set_page_headers(response, limit=limit, offset=offset, has_more=page.has_more)
    return page.items


@router.get("/transactions/{transaction_id}", response_model=BankTransactionRead)
def get_transaction(
    transaction_id: UUID, principal: BankingReadDep, db: SessionDep
) -> BankTransactionRead:
    try:
        return get_bank_transaction(db, principal, transaction_id)
    except BankingDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/transactions/{transaction_id}/reconcile", response_model=BankTransactionRead)
def post_reconcile(
    transaction_id: UUID,
    payload: BankReconcileRequest,
    principal: BankingWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = reconcile_transaction(
            db, transaction_id, payload.payment_id, principal, _key(idempotency_key)
        )
    except BankingDomainError as error:
        raise _error(error) from error
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(BankTransactionRead.model_validate(result.transaction)),
    )


__all__ = ["router"]
