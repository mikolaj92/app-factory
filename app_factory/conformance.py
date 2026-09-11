"""Conformance checks for a thin product host (no generator, no chrome forks)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from fastapi import FastAPI
    from starlette.exceptions import HTTPException
    from starlette.routing import Mount
except ImportError as exc:  # pragma: no cover
    raise ImportError("app_factory.conformance requires app-factory[platform]") from exc

from app_factory.adapters.route_contract import check_identity_routes
from app_factory.csrf import SameOriginCsrfMiddleware
from app_factory.product_errors import product_http_error, product_server_error

__all__ = [
    "FORBIDDEN_IDENTITY_INSTALLERS",
    "HostConformanceError",
    "HostConformanceReport",
    "assert_thin_host",
    "check_thin_host",
    "check_thin_host_sources",
]

FORBIDDEN_IDENTITY_INSTALLERS: tuple[str, ...] = (
    "install_passkey_ui(",
    "install_usermanager_ui(",
)

FORBIDDEN_TEMPLATES: tuple[str, ...] = (
    "product_shell.html",
    "identity_authenticated_shell.html",
    "identity_public_shell.html",
    "identity_denied.html",
    "identity_denied_fragment.html",
    "identity_public_state.html",
    "platform_auth.html",
    "platform_controls.html",
    "platform_sidebar.html",
    "platform_sidebar_foot.html",
    "platform_session.html",
    "platform_theme_locale.html",
    "head_assets.html",
    "head_assets_slim.html",
    "client_shell.html",
    "shell.html",
    "_platform_nav_item.html",
)

FORBIDDEN_ASSETS: tuple[str, ...] = (
    "basecoat-factory.min.css",
    "basecoat-js.min.js",
    "htmx.min.js",
    "alpine.min.js",
    "tailwind.min.js",
    "material-symbols.css",
    "material-symbols-outlined.woff2",
)

_SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "tests",
}

_CORE_ASSET = "basecoat-factory.min.css"


class HostConformanceError(ValueError):
    """The host violates the thin product-host contract."""


@dataclass(frozen=True, slots=True)
class HostConformanceReport:
    static_path: str
    health_path: str | None
    origin_csrf: bool
    htmx_errors: bool


def check_thin_host_sources(
    host_root: str | Path,
    *,
    identity: bool = False,
) -> None:
    """Fail if the host copied chrome templates/assets or called package installers."""
    root = Path(host_root)
    problems: list[str] = []
    python_sources: list[str] = []
    for path in _iter_host_files(root):
        name = path.name
        if name in FORBIDDEN_TEMPLATES:
            problems.append(f"local copy of {name}: {path}")
        if name in FORBIDDEN_ASSETS:
            problems.append(f"local copy of {name}: {path}")
        if path.suffix == ".py":
            text = path.read_text(encoding="utf-8")
            python_sources.append(text)
            for marker in FORBIDDEN_IDENTITY_INSTALLERS:
                if marker in text:
                    problems.append(f"{path} calls {marker.rstrip('(')}")
    if identity and "install_identity_adapters(" not in "\n".join(python_sources):
        problems.append("identity host does not call install_identity_adapters")
    if problems:
        raise HostConformanceError("; ".join(problems))


def check_thin_host(
    app: FastAPI,
    host_root: str | Path,
    *,
    identity: bool = False,
    probe: bool = True,
    page_path: str | None = "/",
    mutation_path: str | None = None,
    health_path: str | None = "/health",
    static_path: str = "/static/platform",
) -> HostConformanceReport:
    """Inspect sources plus the live app for the thin-host contract.

    Chrome-only hosts (``identity=False``) must mount shared static, expose
    health, reject cross-origin unsafe requests, and return HTMX error
    fragments. Identity hosts must not call package UI installers; health and
    Origin CSRF stay optional because those hosts compose adapters themselves.
    """
    check_thin_host_sources(host_root, identity=identity)
    problems: list[str] = []
    expected_static = static_path.rstrip("/")
    if not any(
        isinstance(route, Mount) and route.path.rstrip("/") == expected_static
        for route in app.routes
    ):
        problems.append(f"missing shared static mount at {expected_static}")

    if identity:
        try:
            check_identity_routes(
                app.routes, getattr(app.state, "app_factory_identity_routes", ())
            )
        except ValueError as exc:
            problems.append(str(exc))

    origin_csrf = _has_same_origin_csrf(app)
    htmx_errors = _has_htmx_error_handlers(app)
    if not identity:
        if not origin_csrf:
            problems.append("Origin CSRF middleware is missing")
        if not htmx_errors:
            problems.append("HTMX error handlers are missing")
        if not health_path:
            problems.append("health_path is required for chrome-only hosts")

    if problems:
        raise HostConformanceError("; ".join(problems))

    if probe:
        _probe_runtime(
            app,
            problems,
            identity=identity,
            page_path=page_path,
            mutation_path=mutation_path,
            health_path=health_path,
            static_path=expected_static,
            origin_csrf=origin_csrf,
            htmx_errors=htmx_errors,
        )
        if problems:
            raise HostConformanceError("; ".join(problems))

    return HostConformanceReport(
        static_path=expected_static,
        health_path=health_path,
        origin_csrf=origin_csrf,
        htmx_errors=htmx_errors,
    )


def assert_thin_host(
    app: FastAPI,
    host_root: str | Path,
    *,
    identity: bool = False,
    probe: bool = True,
    page_path: str | None = "/",
    mutation_path: str | None = None,
    health_path: str | None = "/health",
    static_path: str = "/static/platform",
) -> HostConformanceReport:
    return check_thin_host(
        app,
        host_root,
        identity=identity,
        probe=probe,
        page_path=page_path,
        mutation_path=mutation_path,
        health_path=health_path,
        static_path=static_path,
    )


def _iter_host_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in {"uv.lock", "Cargo.lock"}:
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def _has_same_origin_csrf(app: FastAPI) -> bool:
    return any(item.cls is SameOriginCsrfMiddleware for item in app.user_middleware)


def _has_htmx_error_handlers(app: FastAPI) -> bool:
    handlers = app.exception_handlers
    return (
        handlers.get(HTTPException) is product_http_error
        or handlers.get(Exception) is product_server_error
    )


def _probe_runtime(
    app: FastAPI,
    problems: list[str],
    *,
    identity: bool,
    page_path: str | None,
    mutation_path: str | None,
    health_path: str | None,
    static_path: str,
    origin_csrf: bool,
    htmx_errors: bool,
) -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        asset = client.get(f"{static_path}/{_CORE_ASSET}")
        if asset.status_code != 200:
            problems.append(
                f"shared asset {static_path}/{_CORE_ASSET} returned {asset.status_code}"
            )
        if health_path:
            health = client.get(health_path)
            if health.status_code != 200 or health.json() != {"status": "ok"}:
                problems.append(f"health {health_path} is missing or not ok")
        if page_path:
            page = client.get(page_path)
            if page.status_code != 200:
                problems.append(f"page {page_path} returned {page.status_code}")
            elif f"{static_path}/{_CORE_ASSET}" not in page.text:
                problems.append("page does not load shared platform assets")
        if origin_csrf:
            probe_path = mutation_path or health_path or page_path
            if not probe_path:
                problems.append("Origin CSRF probe path is missing")
            else:
                blocked = client.post(
                    probe_path, headers={"Origin": "https://evil.example"}
                )
                if blocked.status_code != 403:
                    problems.append("Origin CSRF did not reject cross-origin POST")
                fragment = client.post(
                    probe_path,
                    headers={
                        "Origin": "https://evil.example",
                        "HX-Request": "true",
                    },
                )
                if (
                    fragment.status_code != 403
                    or 'role="alert"' not in fragment.text
                ):
                    problems.append("HTMX CSRF boundary missing")
        if htmx_errors and not identity:
            missing = client.get(
                "/__app_factory_conformance_missing__",
                headers={"HX-Request": "true"},
            )
            if missing.status_code != 404 or 'role="alert"' not in missing.text:
                problems.append("HTMX error boundary missing")
