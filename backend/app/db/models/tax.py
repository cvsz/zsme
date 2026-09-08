from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy import CheckConstraint, Date, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import IdentifiedTimestampMixin, OrganizationScopeMixin


class TaxRateRule(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    """Effective-dated tax rule metadata; statutory exports live in adapters."""

    __tablename__ = "tax_rate_rules"
    __table_args__ = (
        CheckConstraint(
            "tax_type IN ('vat', 'withholding')",
            name="ck_tax_rate_rules_type",
        ),
        CheckConstraint("rate >= 0 AND rate <= 100", name="ck_tax_rate_rules_rate"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from <= effective_to",
            name="ck_tax_rate_rules_dates",
        ),
        UniqueConstraint(
            "organization_id",
            "tax_type",
            "code",
            "effective_from",
            name="uq_tax_rate_rules_org_type_code_from",
        ),
    )

    tax_type: Mapped[Literal["vat", "withholding"]] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)
    version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)


__all__ = ["TaxRateRule"]
