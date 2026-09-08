from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import OrganizationReadDep, OrganizationWriteDep, SessionDep
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
    principal: OrganizationReadDep, db: SessionDep
) -> list[Organization]:
    return list(
        db.scalars(
            select(Organization)
            .where(Organization.tenant_id == principal.tenant_id)
            .order_by(Organization.slug)
        ).all()
    )


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
