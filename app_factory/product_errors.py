"""Transport-only error defaults for product hosts; no domain error policy."""

from html import escape

from fastapi import Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException


def _error_fragment(request: Request, status: int, detail: str, headers=None):
    if request.headers.get("HX-Request", "").lower() != "true":
        return None
    return HTMLResponse(
        '<div class="alert" data-variant="destructive" role="alert">'
        f"{escape(detail)}</div>",
        status_code=status,
        headers=headers,
    )


def _http_detail(detail: object) -> str:
    if isinstance(detail, str) and detail:
        return detail
    return "Request denied."


async def product_http_error(request: Request, exc: HTTPException):
    if exc.status_code >= 400:
        fragment = _error_fragment(
            request, exc.status_code, _http_detail(exc.detail), exc.headers
        )
        if fragment is not None:
            return fragment
    return await http_exception_handler(request, exc)


async def product_validation_error(request: Request, exc: RequestValidationError):
    fragment = _error_fragment(request, 422, "Invalid request.")
    if fragment is not None:
        return fragment
    return await request_validation_exception_handler(request, exc)


async def product_server_error(request: Request, _exc: Exception):
    fragment = _error_fragment(request, 500, "Internal Server Error")
    if fragment is not None:
        return fragment
    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)
