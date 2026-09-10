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
from app.domains.documents.schemas import DocumentCreate, DocumentRead, DocumentStatus
from app.domains.documents.service import (
    DocumentDomainError,
    create_document,
    get_document,
    list_documents,
    post_document,
)

router = APIRouter(prefix="/v1", tags=["documents"])


def _domain_error(error: DocumentDomainError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


def _document_response(document, response_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=response_status,
        content=jsonable_encoder(DocumentRead.model_validate(document)),
    )


def _require_idempotency_key(idempotency_key: str | None) -> str:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required")
    return idempotency_key


@router.get("/ar/invoices", response_model=list[DocumentRead])
def get_invoices(
    principal: ArReadDep,
    db: SessionDep,
    response: Response,
    document_status: Annotated[DocumentStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
) -> list[DocumentRead]:
    page = list_documents(
        db,
        principal,
        "sales_invoice",
        status=document_status,
        search=search,
        limit=limit,
        offset=offset,
    )
    set_page_headers(response, limit=limit, offset=offset, has_more=page.has_more)
    return page.items


@router.post("/ar/invoices", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def post_invoice(
    payload: DocumentCreate,
    principal: ArWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = create_document(
            db, payload, principal, "sales_invoice", _require_idempotency_key(idempotency_key)
        )
    except DocumentDomainError as error:
        raise _domain_error(error) from error
    return _document_response(result.document, 200 if result.replayed else 201)


@router.get("/ar/invoices/{document_id}", response_model=DocumentRead)
def get_invoice(document_id: UUID, principal: ArReadDep, db: SessionDep) -> DocumentRead:
    try:
        return get_document(db, document_id, principal, "sales_invoice")
    except DocumentDomainError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/ar/invoices/{document_id}/post", response_model=DocumentRead)
def post_invoice_document(
    document_id: UUID,
    principal: ArWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = post_document(
            db,
            document_id,
            principal,
            "sales_invoice",
            _require_idempotency_key(idempotency_key),
        )
    except DocumentDomainError as error:
        raise _domain_error(error) from error
    return _document_response(result.document, 200)


@router.get("/ap/bills", response_model=list[DocumentRead])
def get_bills(
    principal: ApReadDep,
    db: SessionDep,
    response: Response,
    document_status: Annotated[DocumentStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
) -> list[DocumentRead]:
    page = list_documents(
        db,
        principal,
        "vendor_bill",
        status=document_status,
        search=search,
        limit=limit,
        offset=offset,
    )
    set_page_headers(response, limit=limit, offset=offset, has_more=page.has_more)
    return page.items


@router.post("/ap/bills", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def post_bill(
    payload: DocumentCreate,
    principal: ApWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = create_document(
            db, payload, principal, "vendor_bill", _require_idempotency_key(idempotency_key)
        )
    except DocumentDomainError as error:
        raise _domain_error(error) from error
    return _document_response(result.document, 200 if result.replayed else 201)


@router.get("/ap/bills/{document_id}", response_model=DocumentRead)
def get_bill(document_id: UUID, principal: ApReadDep, db: SessionDep) -> DocumentRead:
    try:
        return get_document(db, document_id, principal, "vendor_bill")
    except DocumentDomainError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/ap/bills/{document_id}/post", response_model=DocumentRead)
def post_bill_document(
    document_id: UUID,
    principal: ApWriteDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    try:
        result = post_document(
            db,
            document_id,
            principal,
            "vendor_bill",
            _require_idempotency_key(idempotency_key),
        )
    except DocumentDomainError as error:
        raise _domain_error(error) from error
    return _document_response(result.document, 200)


__all__ = ["router"]
