from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.api.dependencies import ApReadDep, ApWriteDep, ArReadDep, ArWriteDep, SessionDep
from app.core.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_OFFSET,
    MAX_PAGE_SIZE,
    set_page_headers,
)
from app.domains.payments.schemas import PaymentCreate, PaymentRead, PaymentStatus
from app.domains.payments.service import (
    PaymentDomainError,
    create_payment,
    list_payments,
    post_payment,
)

router = APIRouter(prefix="/v1", tags=["payments"])


def _error(error: PaymentDomainError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


def _key(value: str | None) -> str:
    if value is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required")
    return value


def _response(payment, response_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=response_status,
        content=jsonable_encoder(PaymentRead.model_validate(payment)),
    )


@router.get("/ar/receipts", response_model=list[PaymentRead])
def get_receipts(
    principal: ArReadDep,
    db: SessionDep,
    response: Response,
    payment_status: Annotated[PaymentStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
) -> list[PaymentRead]:
    page = list_payments(
        db,
        principal,
        "receipt",
        status=payment_status,
        limit=limit,
        offset=offset,
    )
    set_page_headers(response, limit=limit, offset=offset, has_more=page.has_more)
    return page.items


@router.post("/ar/receipts", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def post_receipt(
    payload: PaymentCreate,
    principal: ArWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = create_payment(db, payload, principal, "receipt", _key(idempotency_key))
    except PaymentDomainError as error:
        raise _error(error) from error
    return _response(result.payment, 200 if result.replayed else 201)


@router.post("/ar/receipts/{payment_id}/post", response_model=PaymentRead)
def post_receipt_payment(
    payment_id: UUID,
    principal: ArWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = post_payment(db, payment_id, principal, "receipt", _key(idempotency_key))
    except PaymentDomainError as error:
        raise _error(error) from error
    return _response(result.payment, 200)


@router.get("/ap/disbursements", response_model=list[PaymentRead])
def get_disbursements(
    principal: ApReadDep,
    db: SessionDep,
    response: Response,
    payment_status: Annotated[PaymentStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
) -> list[PaymentRead]:
    page = list_payments(
        db,
        principal,
        "disbursement",
        status=payment_status,
        limit=limit,
        offset=offset,
    )
    set_page_headers(response, limit=limit, offset=offset, has_more=page.has_more)
    return page.items


@router.post("/ap/disbursements", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def post_disbursement(
    payload: PaymentCreate,
    principal: ApWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = create_payment(db, payload, principal, "disbursement", _key(idempotency_key))
    except PaymentDomainError as error:
        raise _error(error) from error
    return _response(result.payment, 200 if result.replayed else 201)


@router.post("/ap/disbursements/{payment_id}/post", response_model=PaymentRead)
def post_disbursement_payment(
    payment_id: UUID,
    principal: ApWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = post_payment(db, payment_id, principal, "disbursement", _key(idempotency_key))
    except PaymentDomainError as error:
        raise _error(error) from error
    return _response(result.payment, 200)


__all__ = ["router"]
