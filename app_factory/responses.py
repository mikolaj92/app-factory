"""Small HTTP response helpers shared by HTMX hosts."""

from __future__ import annotations

try:
    from fastapi import Request
    from fastapi.responses import RedirectResponse
except ImportError as exc:
    raise ImportError("app_factory.responses requires app-factory[fastapi]") from exc


def htmx_redirect(
    request: Request,
    url: str,
    *,
    status_code: int = 303,
) -> RedirectResponse:
    """Return a native redirect and instruct HTMX to navigate the full page."""
    if not url:
        raise ValueError("url is required")
    response = RedirectResponse(url=url, status_code=status_code)
    if request.headers.get("HX-Request", "").lower() == "true":
        response.headers["HX-Redirect"] = url
    return response
