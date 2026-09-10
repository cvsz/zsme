from __future__ import annotations

import re
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.domains.ledger.service import DomainError
from app.observability.logging import configure_logging, log_request

_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", str(uuid4()))


def _problem(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    fields: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": f"https://zsme.dev/problems/{code}",
        "title": title,
        "status": status_code,
        "code": code,
        "detail": detail,
        "correlation_id": _correlation_id(request),
    }
    if fields:
        body["fields"] = fields
    return JSONResponse(
        body,
        status_code=status_code,
        media_type="application/problem+json",
        headers=headers,
    )


def _http_code(status_code: int) -> tuple[str, str]:
    return {
        400: ("bad_request", "Bad request"),
        401: ("authentication_required", "Authentication required"),
        403: ("forbidden", "Forbidden"),
        404: ("not_found", "Resource not found"),
        405: ("method_not_allowed", "Method not allowed"),
        413: ("request_too_large", "Request entity too large"),
        409: ("conflict", "Conflict"),
        422: ("validation_error", "Validation error"),
        429: ("rate_limited", "Too many requests"),
        500: ("internal_error", "Internal server error"),
        503: ("service_unavailable", "Service unavailable"),
    }.get(status_code, ("http_error", "Request failed"))


def register_exception_handlers(app: FastAPI) -> None:
    configure_logging()

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        started = monotonic()
        supplied = request.headers.get("X-Correlation-ID", "")
        correlation_id = supplied if _CORRELATION_ID.fullmatch(supplied) else str(uuid4())
        request.state.correlation_id = correlation_id
        request_limit = get_settings().request_body_limit_bytes
        content_length = request.headers.get("Content-Length")
        if content_length is not None:
            try:
                request_size = int(content_length)
            except ValueError:
                return _problem(
                    request,
                    status_code=400,
                    code="bad_request",
                    title="Bad request",
                    detail="invalid Content-Length header",
                )
            if request_size > request_limit:
                return _problem(
                    request,
                    status_code=413,
                    code="request_too_large",
                    title="Request entity too large",
                    detail="request body exceeds the configured limit",
                )
        else:
            body_chunks: list[bytes] = []
            received_bytes = 0
            async for chunk in request.stream():
                received_bytes += len(chunk)
                if received_bytes > request_limit:
                    return _problem(
                        request,
                        status_code=413,
                        code="request_too_large",
                        title="Request entity too large",
                        detail="request body exceeds the configured limit",
                    )
                body_chunks.append(chunk)
            request._body = b"".join(body_chunks)
        try:
            response = await call_next(request)
        except Exception:
            log_request(
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=(monotonic() - started) * 1000,
                correlation_id=correlation_id,
                tenant_id=getattr(request.state, "tenant_id", None),
                user_id=getattr(request.state, "user_id", None),
                outcome="exception",
            )
            raise
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = correlation_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if getattr(get_settings(), "environment", "development").lower() in {"production", "prod"}:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        log_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=(monotonic() - started) * 1000,
            correlation_id=correlation_id,
            tenant_id=getattr(request.state, "tenant_id", None),
            user_id=getattr(request.state, "user_id", None),
            outcome="completed" if response.status_code < 400 else "client_error",
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        code, title = _http_code(exc.status_code)
        detail = exc.detail if isinstance(exc.detail, str) else "request failed"
        return _problem(
            request,
            status_code=exc.status_code,
            code=code,
            title=title,
            detail=detail,
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_error_handler(request: Request, exc: StarletteHTTPException):
        code, title = _http_code(exc.status_code)
        detail = exc.detail if isinstance(exc.detail, str) else "request failed"
        return _problem(
            request,
            status_code=exc.status_code,
            code=code,
            title=title,
            detail=detail,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        fields = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": str(error["msg"]),
                "type": str(error["type"]),
            }
            for error in exc.errors()
        ]
        return _problem(
            request,
            status_code=422,
            code="validation_error",
            title="Validation error",
            detail="request validation failed",
            fields=fields,
        )

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        return _problem(
            request,
            status_code=409,
            code="domain_error",
            title="Domain operation rejected",
            detail=str(exc),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, _exc: Exception):
        return _problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal server error",
            detail="the request could not be completed",
        )
