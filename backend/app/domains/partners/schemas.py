from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

PartnerType = Literal["customer", "vendor", "both"]
AddressType = Literal["registered", "billing", "shipping", "other"]


class PartnerCreate(BaseModel):
    partner_code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    partner_type: PartnerType
    display_name: str = Field(min_length=1, max_length=250)
    legal_name: str | None = Field(default=None, max_length=250)
    tax_id: str | None = Field(default=None, max_length=32)
    tax_branch: str = Field(default="00000", min_length=1, max_length=20)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    payment_terms_days: int = Field(default=0, ge=0, le=3650)
    credit_limit: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=18, decimal_places=2)
    tags: list[str] = Field(default_factory=list, max_length=20)


class PartnerUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=250)
    legal_name: str | None = Field(default=None, max_length=250)
    tax_id: str | None = Field(default=None, max_length=32)
    tax_branch: str | None = Field(default=None, min_length=1, max_length=20)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    credit_limit: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    tags: list[str] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def require_change(self) -> PartnerUpdate:
        if not any(
            value is not None
            for field, value in self.model_dump().items()
            if field != "expected_version"
        ):
            raise ValueError("at least one partner field must change")
        return self


class PartnerArchive(BaseModel):
    expected_version: int = Field(ge=1)


class PartnerAddressCreate(BaseModel):
    address_type: AddressType = "other"
    label: str | None = Field(default=None, max_length=100)
    address_line1: str = Field(min_length=1, max_length=250)
    address_line2: str | None = Field(default=None, max_length=250)
    district: str | None = Field(default=None, max_length=120)
    province: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=20)
    country_code: str = Field(default="TH", min_length=2, max_length=2)
    is_primary: bool = False


class PartnerAddressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    partner_id: UUID
    address_type: AddressType
    label: str | None
    address_line1: str
    address_line2: str | None
    district: str | None
    province: str | None
    postal_code: str | None
    country_code: str
    is_primary: bool


class PartnerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    organization_id: UUID
    partner_code: str
    partner_type: PartnerType
    display_name: str
    legal_name: str | None
    tax_id: str | None
    tax_branch: str
    email: str | None
    phone: str | None
    payment_terms_days: int
    credit_limit: Decimal
    is_active: bool
    version: int
    tags: list[str]
    addresses: list[PartnerAddressRead] = Field(default_factory=list)


__all__ = [
    "AddressType",
    "PartnerAddressCreate",
    "PartnerAddressRead",
    "PartnerArchive",
    "PartnerCreate",
    "PartnerRead",
    "PartnerType",
    "PartnerUpdate",
]
