from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import Principal
from app.db.models import Organization


class CurrencyPolicyError(Exception):
    """A request violates the current base-currency-only accounting policy."""


def organization_currency(db: Session, principal: Principal) -> str:
    if principal.organization_id is None:
        raise CurrencyPolicyError("an organization is required for currency validation")
    value = db.scalar(
        select(Organization.default_currency).where(
            Organization.id == principal.organization_id,
            Organization.tenant_id == principal.tenant_id,
        )
    )
    if value is None:
        raise CurrencyPolicyError("organization not found")
    return value.strip().upper()


def enforce_base_currency(db: Session, principal: Principal, currency_code: str) -> str:
    expected = organization_currency(db, principal)
    actual = currency_code.strip().upper()
    if actual != expected:
        raise CurrencyPolicyError(
            f"multi-currency posting is not supported yet; organization currency is {expected}"
        )
    return actual


__all__ = ["CurrencyPolicyError", "enforce_base_currency", "organization_currency"]
