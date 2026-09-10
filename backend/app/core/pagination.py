from __future__ import annotations

from dataclasses import dataclass

from fastapi import Response

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500
MAX_PAGE_OFFSET = 1_000_000


@dataclass(frozen=True)
class Page[T]:
    items: list[T]
    has_more: bool


def set_page_headers(response: Response, *, limit: int, offset: int, has_more: bool) -> None:
    response.headers["X-Page-Limit"] = str(limit)
    response.headers["X-Page-Offset"] = str(offset)
    response.headers["X-Page-Has-More"] = "true" if has_more else "false"


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_OFFSET",
    "MAX_PAGE_SIZE",
    "Page",
    "set_page_headers",
]
