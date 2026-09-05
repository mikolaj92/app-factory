"""Small HTTP response helpers shared by HTMX hosts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import HTMLResponse, RedirectResponse
    from jinja2 import Environment
except ImportError as exc:
    raise ImportError("app_factory.responses requires app-factory[fastapi]") from exc


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
    """
    selected = (
        fragment_template
        if fragment_template
        and request.headers.get("HX-Request", "").lower() == "true"
        else template
    )
    values = dict(
        getattr(request.state, "app_factory_platform_context", {}) or {}
    )
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
