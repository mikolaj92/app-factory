"""Internal product-host error defaults; product error policy stays host-owned."""

from html import escape

from fastapi import Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException


def _fragment(request: Request, status: int, detail: str, headers=None):
    if request.headers.get("HX-Request", "").lower() != "true":
        return None
    return HTMLResponse(
        '<div class="alert" data-variant="destructive" role="alert">'
        f"{escape(detail)}</div>",
        status_code=status,
        headers=headers,
    )


async def product_http_error(request: Request, exc: HTTPException):
    # Preserve no-body statuses and headers (e.g. WWW-Authenticate).
    if exc.status_code >= 400:
        fragment = _fragment(request, exc.status_code, str(exc.detail), exc.headers)
        if fragment is not None:
            return fragment
    return await http_exception_handler(request, exc)


async def product_validation_error(request: Request, exc: RequestValidationError):
    fragment = _fragment(request, 422, "Invalid request.")
    if fragment is not None:
        return fragment
    return await request_validation_exception_handler(request, exc)


async def product_server_error(request: Request, _exc: Exception):
    fragment = _fragment(request, 500, "Internal Server Error")
    if fragment is not None:
        return fragment
    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)
