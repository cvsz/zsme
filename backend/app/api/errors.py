from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from app.domains.ledger.service import DomainError


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
    return JSONResponse(body, status_code=status_code, media_type="application/problem+json")


def _http_code(status_code: int) -> tuple[str, str]:
    return {
        400: ("bad_request", "Bad request"),
        401: ("authentication_required", "Authentication required"),
        403: ("forbidden", "Forbidden"),
        404: ("not_found", "Resource not found"),
        405: ("method_not_allowed", "Method not allowed"),
        409: ("conflict", "Conflict"),
        422: ("validation_error", "Validation error"),
        429: ("rate_limited", "Too many requests"),
        500: ("internal_error", "Internal server error"),
        503: ("service_unavailable", "Service unavailable"),
    }.get(status_code, ("http_error", "Request failed"))


def register_exception_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        supplied = request.headers.get("X-Correlation-ID", "")
        correlation_id = supplied if 0 < len(supplied) <= 100 else str(uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
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
