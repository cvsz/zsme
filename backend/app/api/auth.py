from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.dependencies import PrincipalDep, SessionDep
from app.core.auth import (
    AUTH_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    create_session,
    refresh_csrf_token,
    revoke_session,
)
from app.core.config import get_settings
from app.core.login_throttle import (
    LoginRateLimitError,
    check_login_throttle,
    login_bucket_keys,
    record_login_failure,
    record_login_success,
)
from app.core.security import dummy_password_hash, verify_password
from app.db.models import Organization, Tenant, User

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int
    csrf_token: str


class CsrfResponse(BaseModel):
    csrf_token: str


class MeResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID
    organization_id: UUID | None
    organization_currency: str | None
    organization_timezone: str | None
    email: str
    display_name: str
    roles: list[str]
    permissions: list[str]


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest, request: Request, response: Response, db: SessionDep
) -> LoginResponse:
    normalized_email = payload.email.strip().lower()
    bucket_keys = login_bucket_keys(request, payload.tenant_slug, normalized_email)
    try:
        check_login_throttle(db, bucket_keys)
    except LoginRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(error),
            headers={"Retry-After": str(error.retry_after)},
        ) from error
    user = db.scalar(
        select(User)
        .join(Tenant, User.tenant_id == Tenant.id)
        .where(Tenant.slug == payload.tenant_slug.strip().lower())
        .where(Tenant.status == "active")
        .where(func.lower(User.email) == normalized_email)
        .where(User.is_active.is_(True))
    )
    password_hash = user.password_hash if user is not None else dummy_password_hash()
    if not verify_password(payload.password, password_hash):
        retry_after = record_login_failure(db, bucket_keys)
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="too many login attempts",
                headers={"Retry-After": str(retry_after)},
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    record_login_success(db, bucket_keys)
    access_token, csrf_token = create_session(db, user)
    settings = get_settings()
    expires_in = settings.access_token_ttl_minutes * 60
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=access_token,
        max_age=expires_in,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=expires_in,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    login_response = LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        csrf_token=csrf_token,
    )
    request.state.tenant_id = str(user.tenant_id)
    request.state.user_id = str(user.id)
    return login_response


@router.get("/csrf", response_model=CsrfResponse)
def csrf(
    principal: PrincipalDep,
    response: Response,
    db: SessionDep,
) -> CsrfResponse:
    csrf_token = refresh_csrf_token(db, principal)
    settings = get_settings()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return CsrfResponse(csrf_token=csrf_token)


@router.get("/me", response_model=MeResponse)
def me(principal: PrincipalDep, db: SessionDep) -> MeResponse:
    organization = (
        db.scalar(
            select(Organization).where(
                Organization.id == principal.organization_id,
                Organization.tenant_id == principal.tenant_id,
            )
        )
        if principal.organization_id is not None
        else None
    )
    return MeResponse(
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        organization_id=principal.organization_id,
        organization_currency=organization.default_currency if organization else None,
        organization_timezone=organization.timezone if organization else None,
        email=principal.email,
        display_name=principal.display_name,
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    principal: PrincipalDep,
    response: Response,
    db: SessionDep,
) -> Response:
    revoke_session(db, principal)
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


__all__ = ["router"]
