from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.api.dependencies import OrganizationReadDep, OrganizationWriteDep, SessionDep
from app.db.models import AuditEvent, Role, User, UserRole

router = APIRouter(prefix="/v1/access", tags=["access"])


class RoleRead(BaseModel):
    id: UUID
    name: str
    permissions: list[str]
    is_system: bool


class UserAccessRead(BaseModel):
    id: UUID
    email: str
    display_name: str
    organization_id: UUID | None
    is_active: bool
    roles: list[RoleRead]


class UserRoleUpdate(BaseModel):
    role_ids: list[UUID] = Field(default_factory=list, max_length=50)


def _role_read(role: Role) -> RoleRead:
    return RoleRead(
        id=role.id,
        name=role.name,
        permissions=sorted(role.permissions or []),
        is_system=role.is_system,
    )


def _user_read(user: User) -> UserAccessRead:
    return UserAccessRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        organization_id=user.organization_id,
        is_active=user.is_active,
        roles=sorted((_role_read(role) for role in user.roles), key=lambda role: role.name),
    )


@router.get("/users", response_model=list[UserAccessRead])
def list_access_users(
    principal: OrganizationReadDep,
    db: SessionDep,
) -> list[UserAccessRead]:
    if principal.organization_id is None:
        return []
    users = db.scalars(
        select(User)
        .options(selectinload(User.roles))
        .where(
            User.tenant_id == principal.tenant_id,
            User.organization_id == principal.organization_id,
        )
        .order_by(User.email)
    ).all()
    return [_user_read(user) for user in users]


@router.get("/roles", response_model=list[RoleRead])
def list_access_roles(
    principal: OrganizationReadDep,
    db: SessionDep,
) -> list[RoleRead]:
    roles = db.scalars(
        select(Role)
        .where(Role.tenant_id == principal.tenant_id)
        .order_by(Role.name)
    ).all()
    return [_role_read(role) for role in roles]


@router.put("/users/{user_id}/roles", response_model=UserAccessRead)
def replace_user_roles(
    user_id: UUID,
    payload: UserRoleUpdate,
    principal: OrganizationWriteDep,
    db: SessionDep,
) -> UserAccessRead:
    if principal.organization_id is None:
        raise HTTPException(status_code=409, detail="an organization is required")
    if user_id == principal.user_id:
        raise HTTPException(
            status_code=409,
            detail="operators cannot change their own role assignments",
        )

    user = db.scalar(
        select(User)
        .where(
            User.id == user_id,
            User.tenant_id == principal.tenant_id,
            User.organization_id == principal.organization_id,
        )
        .with_for_update()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    requested_ids = set(payload.role_ids)
    roles = list(
        db.scalars(
            select(Role)
            .where(
                Role.tenant_id == principal.tenant_id,
                Role.id.in_(requested_ids),
            )
            .order_by(Role.name)
        ).all()
    ) if requested_ids else []
    if {role.id for role in roles} != requested_ids:
        raise HTTPException(status_code=404, detail="one or more roles were not found")

    existing_ids = set(
        db.scalars(
            select(UserRole.role_id).where(
                UserRole.tenant_id == principal.tenant_id,
                UserRole.user_id == user.id,
            )
        ).all()
    )
    if existing_ids != requested_ids:
        db.execute(
            delete(UserRole).where(
                UserRole.tenant_id == principal.tenant_id,
                UserRole.user_id == user.id,
            )
        )
        db.add_all(
            UserRole(
                tenant_id=principal.tenant_id,
                user_id=user.id,
                role_id=role_id,
            )
            for role_id in sorted(requested_ids, key=str)
        )
        db.add(
            AuditEvent(
                tenant_id=principal.tenant_id,
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                action="access.roles.update",
                entity_type="user",
                entity_id=user.id,
                correlation_id=principal.correlation_id or str(uuid4()),
                payload={
                    "previous_role_ids": sorted(str(role_id) for role_id in existing_ids),
                    "role_ids": sorted(str(role_id) for role_id in requested_ids),
                },
            )
        )
        db.flush()

    refreshed = db.scalar(
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user.id)
    )
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return _user_read(refreshed)


__all__ = ["router"]
