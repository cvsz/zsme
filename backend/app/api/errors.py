from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
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


def register_exception_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        supplied = request.headers.get("X-Correlation-ID", "")
        correlation_id = supplied if 0 < len(supplied) <= 100 else str(uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

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

