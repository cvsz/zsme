from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import OrganizationReadDep, OrganizationWriteDep, SessionDep
from app.core.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_OFFSET,
    MAX_PAGE_SIZE,
    set_page_headers,
)
from app.db.models import Organization

router = APIRouter(prefix="/v1/organizations", tags=["organizations"])


class OrganizationCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    legal_name: str = Field(min_length=1, max_length=250)
    default_currency: str = Field(default="THB", min_length=3, max_length=3)
    timezone: str = Field(default="Asia/Bangkok", min_length=1, max_length=64)
    vat_registered: bool = False
    vat_rate: Decimal = Field(default=Decimal("7.00"), ge=0, le=100, decimal_places=2)


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    slug: str
    legal_name: str
    default_currency: str
    timezone: str
    vat_registered: bool
    vat_rate: Decimal


@router.get("", response_model=list[OrganizationRead])
def list_organizations(
    principal: OrganizationReadDep,
    db: SessionDep,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
) -> list[Organization]:
    organizations = list(
        db.scalars(
            select(Organization)
            .where(Organization.tenant_id == principal.tenant_id)
            .order_by(Organization.slug)
            .offset(offset)
            .limit(limit + 1)
        ).all()
    )
    has_more = len(organizations) > limit
    set_page_headers(response, limit=limit, offset=offset, has_more=has_more)
    return organizations[:limit]


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    principal: OrganizationWriteDep,
    db: SessionDep,
) -> Organization:
    organization = Organization(
        tenant_id=principal.tenant_id,
        slug=payload.slug.lower(),
        legal_name=payload.legal_name.strip(),
        default_currency=payload.default_currency.upper(),
        timezone=payload.timezone,
        vat_registered=payload.vat_registered,
        vat_rate=payload.vat_rate,
    )
    db.add(organization)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="organization slug already exists") from error
    return organization


__all__ = ["router"]
