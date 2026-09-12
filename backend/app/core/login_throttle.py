from __future__ import annotations

import hmac
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import LoginThrottle


@dataclass(frozen=True)
class LoginRateLimitError(Exception):
    retry_after: int

    def __str__(self) -> str:
        return "too many login attempts"


def _client_host(request: Request) -> str:
    client_host = request.client.host if request.client is not None else "unknown"
    try:
        peer = ip_address(client_host)
    except ValueError:
        return client_host

    trusted = get_settings().trusted_proxy_network_list
    if not any(peer in ip_network(network, strict=False) for network in trusted):
        return client_host

    forwarded = request.headers.get("X-Forwarded-For", "")
    candidate = forwarded.split(",", maxsplit=1)[0].strip()
    if not candidate:
        return client_host
    try:
        return str(ip_address(candidate))
    except ValueError:
        return client_host


def login_bucket_keys(request: Request, tenant_slug: str, email: str) -> tuple[str, str]:
    client_host = _client_host(request)
    normalized_tenant = tenant_slug.strip().lower()
    identity = f"identity:{normalized_tenant}:{email.strip().lower()}"
    network = f"network:{normalized_tenant}:{client_host}"
    return (_bucket_key(identity), _bucket_key(network))


def check_login_throttle(
    db: Session,
    bucket_keys: tuple[str, ...],
    now: datetime | None = None,
) -> None:
    current = now or datetime.now(UTC)
    settings = get_settings()
    records = list(
        db.scalars(
            select(LoginThrottle)
            .where(LoginThrottle.bucket_key.in_(bucket_keys))
            .with_for_update()
        ).all()
    )
    for record in records:
        blocked_until = _utc(record.blocked_until)
        if blocked_until is not None and blocked_until > current:
            retry_after = max(1, int((blocked_until - current).total_seconds()) + 1)
            raise LoginRateLimitError(retry_after)
        if current - _utc(record.window_started_at) >= timedelta(
            seconds=settings.login_window_seconds
        ):
            record.failed_attempts = 0
            record.window_started_at = current
            record.blocked_until = None
    if records:
        db.flush()


def record_login_failure(
    db: Session,
    bucket_keys: tuple[str, ...],
    now: datetime | None = None,
) -> int | None:
    current = now or datetime.now(UTC)
    settings = get_settings()
    retry_after: int | None = None
    for bucket_key in bucket_keys:
        record = _get_or_create(db, bucket_key, current)
        if current - _utc(record.window_started_at) >= timedelta(
            seconds=settings.login_window_seconds
        ):
            record.failed_attempts = 0
            record.window_started_at = current
            record.blocked_until = None
        record.failed_attempts += 1
        record.last_failed_at = current
        if record.failed_attempts >= settings.login_max_failures:
            record.blocked_until = current + timedelta(seconds=settings.login_block_seconds)
            retry = max(1, int((record.blocked_until - current).total_seconds()) + 1)
            retry_after = max(retry_after or 0, retry)
    db.flush()
    return retry_after


def record_login_success(db: Session, bucket_keys: tuple[str, ...]) -> None:
    db.execute(delete(LoginThrottle).where(LoginThrottle.bucket_key.in_(bucket_keys)))
    db.flush()


def _bucket_key(value: str) -> str:
    secret = get_settings().secret_key.encode("utf-8")
    return hmac.new(secret, value.encode("utf-8"), sha256).hexdigest()


def _get_or_create(db: Session, bucket_key: str, now: datetime) -> LoginThrottle:
    record = db.scalar(
        select(LoginThrottle).where(LoginThrottle.bucket_key == bucket_key).with_for_update()
    )
    if record is not None:
        return record
    candidate = LoginThrottle(bucket_key=bucket_key, window_started_at=now)
    try:
        with db.begin_nested():
            db.add(candidate)
            db.flush()
        return candidate
    except IntegrityError:
        record = db.scalar(
            select(LoginThrottle).where(LoginThrottle.bucket_key == bucket_key).with_for_update()
        )
        if record is None:  # pragma: no cover - defensive isolation guard
            raise
        return record


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=UTC)
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


__all__ = [
    "LoginRateLimitError",
    "check_login_throttle",
    "login_bucket_keys",
    "record_login_failure",
    "record_login_success",
]
