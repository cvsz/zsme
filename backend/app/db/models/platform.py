from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import IdentifiedTimestampMixin, TenantScopeMixin


class Tenant(IdentifiedTimestampMixin, Base):
    __tablename__ = "tenants"

    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    organizations: Mapped[list[Organization]] = relationship(back_populates="tenant")
    users: Mapped[list[User]] = relationship(back_populates="tenant")
    roles: Mapped[list[Role]] = relationship(back_populates="tenant")


class Organization(IdentifiedTimestampMixin, TenantScopeMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_organizations_tenant_slug"),)

    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(250), nullable=False)
    default_currency: Mapped[str] = mapped_column(String(3), default="THB", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Bangkok", nullable=False)
    vat_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("7.00"), nullable=False
    )

    tenant: Mapped[Tenant] = relationship(back_populates="organizations")
    users: Mapped[list[User]] = relationship(back_populates="organization")


class User(IdentifiedTimestampMixin, TenantScopeMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    organization_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="users")
    organization: Mapped[Organization | None] = relationship(back_populates="users")
    roles: Mapped[list[Role]] = relationship(secondary="user_roles", back_populates="users")
    sessions: Mapped[list[SessionToken]] = relationship(back_populates="user")
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="actor")


class Role(IdentifiedTimestampMixin, TenantScopeMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="roles")
    users: Mapped[list[User]] = relationship(secondary="user_roles", back_populates="roles")


class UserRole(TenantScopeMixin, Base):
    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class SessionToken(IdentifiedTimestampMixin, TenantScopeMixin, Base):
    __tablename__ = "session_tokens"

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class AuditEvent(IdentifiedTimestampMixin, TenantScopeMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_org_created", "organization_id", "created_at"),
        Index("ix_audit_events_org_action_created", "organization_id", "action", "created_at"),
    )

    organization_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    actor: Mapped[User | None] = relationship(back_populates="audit_events")


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def prevent_audit_event_mutation(_mapper, _connection, _target: AuditEvent) -> None:
    raise ValueError("audit events are append-only")


class IdempotencyRecord(IdentifiedTimestampMixin, TenantScopeMixin, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "organization_id", "key", name="uq_idempotency_tenant_org_key"
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    operation: Mapped[str] = mapped_column(String(150), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    response_status: Mapped[int] = mapped_column(nullable=False)
    response_body: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


__all__ = [
    "AuditEvent",
    "IdempotencyRecord",
    "Organization",
    "Role",
    "SessionToken",
    "Tenant",
    "User",
    "UserRole",
]
