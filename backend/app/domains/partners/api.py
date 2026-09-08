from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.api.dependencies import PartnerReadDep, PartnerWriteDep, SessionDep
from app.domains.partners.schemas import (
    PartnerArchive,
    PartnerCreate,
    PartnerRead,
    PartnerType,
    PartnerUpdate,
)
from app.domains.partners.service import (
    PartnerDomainError,
    archive_partner,
    create_partner,
    get_partner,
    list_partners,
    update_partner,
)

router = APIRouter(prefix="/v1/partners", tags=["partners"])


def _domain_error(error: PartnerDomainError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


def _partner_response(partner, response_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=response_status,
        content=jsonable_encoder(PartnerRead.model_validate(partner)),
    )


@router.get("", response_model=list[PartnerRead])
def get_partners(
    principal: PartnerReadDep,
    db: SessionDep,
    partner_type: Annotated[PartnerType | None, Query(alias="type")] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    include_archived: bool = False,
) -> list:
    return list_partners(
        db,
        principal,
        partner_type=partner_type,
        search=search,
        include_archived=include_archived,
    )


@router.get("/{partner_id}", response_model=PartnerRead)
def get_partner_by_id(partner_id: UUID, principal: PartnerReadDep, db: SessionDep):
    try:
        return get_partner(db, partner_id, principal)
    except PartnerDomainError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("", response_model=PartnerRead, status_code=status.HTTP_201_CREATED)
def post_partner(
    payload: PartnerCreate,
    principal: PartnerWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required")
    try:
        result = create_partner(db, payload, principal, idempotency_key)
    except PartnerDomainError as error:
        raise _domain_error(error) from error
    return _partner_response(result.partner, 200 if result.replayed else 201)


@router.patch("/{partner_id}", response_model=PartnerRead)
def patch_partner(
    partner_id: UUID,
    payload: PartnerUpdate,
    principal: PartnerWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required")
    try:
        result = update_partner(db, partner_id, payload, principal, idempotency_key)
    except PartnerDomainError as error:
        raise _domain_error(error) from error
    return _partner_response(result.partner, 200)


@router.post("/{partner_id}/archive", response_model=PartnerRead)
def post_archive(
    partner_id: UUID,
    payload: PartnerArchive,
    principal: PartnerWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required")
    try:
        result = archive_partner(
            db,
            partner_id,
            payload.expected_version,
            principal,
            idempotency_key,
        )
    except PartnerDomainError as error:
        raise _domain_error(error) from error
    return _partner_response(result.partner, 200)


__all__ = ["router"]
