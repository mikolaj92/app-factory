"""Small HTTP response helpers shared by HTMX hosts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlsplit

try:
    from fastapi import Request
    from fastapi.responses import HTMLResponse, RedirectResponse
    from jinja2 import Environment
except ImportError as exc:
    raise ImportError("app_factory.responses requires app-factory[platform]") from exc


def wants_htmx_fragment(request: Request) -> bool:
    """True for HTMX swaps; false for native navigation and history restore."""
    if request.headers.get("HX-Request", "").lower() != "true":
        return False
    return request.headers.get("HX-History-Restore-Request", "").lower() != "true"


def template_response(
    environment: Environment,
    request: Request,
    template: str,
    context: Mapping[str, Any] | None = None,
    *,
    fragment_template: str | None = None,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
) -> HTMLResponse:
    """Render an explicit full page or HTMX fragment with request context.

    Host values override platform defaults. No template naming conventions,
    database access, or domain error policy are hidden in this helper.
    History restore always receives the full page template.
    """
    selected = (
        fragment_template
        if fragment_template and wants_htmx_fragment(request)
        else template
    )
    values = dict(getattr(request.state, "app_factory_platform_context", {}) or {})
    if context:
        values.update(context)
    values["request"] = request
    rendered = environment.get_template(selected).render(**values)
    return HTMLResponse(rendered, status_code=status_code, headers=dict(headers or {}))


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


def same_origin_return_path(value: str | None) -> str | None:
    """Accept only a same-origin path (my-auth login ``?next=`` rule)."""
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or " " in value
    ):
        return None
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or parts.fragment:
        return None
    return value


def login_redirect(
    request: Request,
    login_path: str = "/login",
    *,
    status_code: int = 303,
) -> RedirectResponse:
    """303 to login with ``?next=`` and ``HX-Redirect`` for HTMX swaps."""
    if not login_path.startswith("/") or login_path.startswith("//"):
        raise ValueError("login_path must be an absolute same-origin path")
    login_parts = urlsplit(login_path)
    if login_parts.scheme or login_parts.netloc or login_parts.fragment:
        raise ValueError("login_path must be an absolute same-origin path")
    login_only = login_parts.path or "/login"
    current = request.url.path
    if request.url.query:
        current = f"{current}?{request.url.query}"
    if current == login_only or current.startswith(f"{login_only}?"):
        return htmx_redirect(request, login_path, status_code=status_code)
    next_path = same_origin_return_path(current)
    if next_path is None:
        return htmx_redirect(request, login_path, status_code=status_code)
    encoded = quote(next_path, safe="/")
    separator = "&" if login_parts.query else "?"
    return htmx_redirect(
        request,
        f"{login_path}{separator}next={encoded}",
        status_code=status_code,
    )
