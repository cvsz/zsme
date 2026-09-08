from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import SessionToken, User
from app.db.session import get_session


@dataclass(frozen=True)
class Principal:
    session_id: UUID
    user_id: UUID
    tenant_id: UUID
    organization_id: UUID | None
    email: str
    display_name: str
    roles: frozenset[str]
    permissions: frozenset[str]


def _token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User) -> str:
    raw_token = token_urlsafe(48)
    session = SessionToken(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=_token_hash(raw_token),
        expires_at=datetime.now(UTC) + timedelta(minutes=get_settings().access_token_ttl_minutes),
    )
    db.add(session)
    db.flush()
    return raw_token


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_principal(
    request: Request, db: Annotated[Session, Depends(get_session)]
) -> Principal:
    authorization = request.headers.get("Authorization", "")
    scheme, _, raw_token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not raw_token:
        raise _unauthorized()

    session = db.scalar(
        select(SessionToken)
        .where(SessionToken.token_hash == _token_hash(raw_token.strip()))
        .where(SessionToken.revoked_at.is_(None))
    )
    if session is None:
        raise _unauthorized()

    now = datetime.now(UTC)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now or not session.user.is_active:
        raise _unauthorized()

    roles = frozenset(role.name for role in session.user.roles)
    permissions = frozenset(
        permission for role in session.user.roles for permission in (role.permissions or [])
    )
    return Principal(
        session_id=session.id,
        user_id=session.user.id,
        tenant_id=session.tenant_id,
        organization_id=session.user.organization_id,
        email=session.user.email,
        display_name=session.user.display_name,
        roles=roles,
        permissions=permissions,
    )


PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


def revoke_session(db: Session, principal: Principal) -> None:
    session = db.get(SessionToken, principal.session_id)
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.flush()


def require_permission(permission: str):
    def dependency(principal: PrincipalDependency) -> Principal:
        if permission not in principal.permissions and "*" not in principal.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return principal

    return dependency


__all__ = [
    "Principal",
    "create_session",
    "get_current_principal",
    "require_permission",
    "revoke_session",
]
