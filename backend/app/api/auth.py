from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Response, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.dependencies import PrincipalDep, SessionDep
from app.core.auth import create_session, revoke_session
from app.core.config import get_settings
from app.core.security import verify_password
from app.db.models import Tenant, User

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int


class MeResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID
    organization_id: UUID | None
    email: str
    display_name: str
    roles: list[str]
    permissions: list[str]


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: SessionDep) -> LoginResponse:
    normalized_email = payload.email.strip().lower()
    user = db.scalar(
        select(User)
        .join(Tenant, User.tenant_id == Tenant.id)
        .where(Tenant.slug == payload.tenant_slug.strip().lower())
        .where(func.lower(User.email) == normalized_email)
        .where(User.is_active.is_(True))
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    access_token = create_session(db, user)
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=get_settings().access_token_ttl_minutes * 60,
    )


@router.get("/me", response_model=MeResponse)
def me(principal: PrincipalDep) -> MeResponse:
    return MeResponse(
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        organization_id=principal.organization_id,
        email=principal.email,
        display_name=principal.display_name,
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    principal: PrincipalDep,
    db: SessionDep,
) -> Response:
    revoke_session(db, principal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
