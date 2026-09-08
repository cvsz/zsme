from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import IdentifiedTimestampMixin, OrganizationScopeMixin


class BusinessPartner(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    __tablename__ = "business_partners"
    __table_args__ = (
        CheckConstraint(
            "partner_type IN ('customer', 'vendor', 'both')",
            name="ck_business_partners_type",
        ),
        CheckConstraint("credit_limit >= 0", name="ck_business_partners_credit_limit"),
        CheckConstraint("payment_terms_days >= 0", name="ck_business_partners_payment_terms"),
        UniqueConstraint(
            "organization_id", "partner_code", name="uq_business_partners_org_code"
        ),
    )

    partner_code: Mapped[str] = mapped_column(String(64), nullable=False)
    partner_type: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(250), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(250), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tax_branch: Mapped[str] = mapped_column(String(20), default="00000", nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(default=0, nullable=False)
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), server_default="0", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    addresses: Mapped[list[PartnerAddress]] = relationship(
        back_populates="partner",
        cascade="all, delete-orphan",
        order_by="PartnerAddress.is_primary.desc()",
    )


class PartnerAddress(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    __tablename__ = "partner_addresses"
    __table_args__ = (
        CheckConstraint(
            "address_type IN ('registered', 'billing', 'shipping', 'other')",
            name="ck_partner_addresses_type",
        ),
    )

    partner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("business_partners.id", ondelete="RESTRICT"), nullable=False
    )
    address_type: Mapped[str] = mapped_column(String(20), default="other", nullable=False)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_line1: Mapped[str] = mapped_column(String(250), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(250), nullable=True)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    province: Mapped[str | None] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), default="TH", nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    partner: Mapped[BusinessPartner] = relationship(back_populates="addresses")


__all__ = ["BusinessPartner", "PartnerAddress"]
