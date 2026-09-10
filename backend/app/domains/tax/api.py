from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.api.dependencies import SessionDep, TaxReadDep, TaxWriteDep
from app.core.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_OFFSET,
    MAX_PAGE_SIZE,
    set_page_headers,
)
from app.domains.tax.schemas import TaxRateCreate, TaxRateRead, TaxType
from app.domains.tax.service import TaxDomainError, create_rate, effective_rate, list_rates

router = APIRouter(prefix="/v1/tax", tags=["tax"])


def _error(error: TaxDomainError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


def _key(value: str | None) -> str:
    if value is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required")
    return value


@router.get("/rates", response_model=list[TaxRateRead])
def get_rates(
    principal: TaxReadDep,
    db: SessionDep,
    response: Response,
    tax_type: Annotated[TaxType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
) -> list[TaxRateRead]:
    page = list_rates(db, principal, tax_type, limit=limit, offset=offset)
    set_page_headers(response, limit=limit, offset=offset, has_more=page.has_more)
    return page.items


@router.post("/rates", response_model=TaxRateRead, status_code=status.HTTP_201_CREATED)
def post_rate(
    payload: TaxRateCreate,
    principal: TaxWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = create_rate(db, payload, principal, _key(idempotency_key))
    except TaxDomainError as error:
        raise _error(error) from error
    return JSONResponse(
        status_code=200 if result.replayed else 201,
        content=jsonable_encoder(TaxRateRead.model_validate(result.rule)),
    )


@router.get("/rates/effective", response_model=TaxRateRead)
def get_effective_rate(
    principal: TaxReadDep,
    db: SessionDep,
    tax_type: TaxType,
    code: str,
    on_date: date,
) -> TaxRateRead:
    try:
        return effective_rate(db, principal, tax_type, code, on_date)
    except TaxDomainError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


__all__ = ["router"]
