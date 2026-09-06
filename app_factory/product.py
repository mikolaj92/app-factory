"""Thin FastAPI host composition; persistence and product policy stay outside."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field, replace
from html import escape
from pathlib import Path
from functools import partial
from re import Pattern

from fastapi import APIRouter, FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException
from jinja2 import Environment
from starlette.routing import BaseRoute, Mount, compile_path
from starlette.types import Lifespan

from app_factory.adapters import (
    IdentityInstall,
    PasskeyBinding,
    UserManagerBinding,
    install_identity_adapters,
    install_platform_request_context,
)
from app_factory.adapters.session import CurrentUser, PageLocales
from app_factory.csrf import SameOriginCsrfMiddleware
from app_factory.assets import platform_asset_url
from app_factory.platform import (
    PlatformConfig,
    PlatformInstall,
    install_platform,
    join_platform_root,
)


@dataclass(frozen=True, slots=True)
class ProductAppConfig:
    """Declarative non-domain host settings."""

    platform: PlatformConfig = field(default_factory=PlatformConfig)
    template_directory: str | Path = "templates"
    static_path: str = "/static/platform"
    mount_name: str = "app-factory-platform"
    health_path: str = "/health"
    csrf_trusted_origins: tuple[str, ...] = ()
    csrf_exempt_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProductInstall:
    environment: Environment
    platform: PlatformInstall
    identity: IdentityInstall | None = None


@dataclass(frozen=True)
class RoutePath:
    path: str
    regex: Pattern[str]
    name: str | None
    methods: frozenset[str]
    mount: bool


def route_paths(routes: Iterable[BaseRoute], prefix: str = "") -> Iterator[RoutePath]:
    """Flatten lazy includes (new FastAPI) without changing routing behavior."""
    for route in routes:
        included = getattr(route, "original_router", None)
        if included is not None:
            nested_prefix = getattr(getattr(route, "include_context", None), "prefix", None)
            if nested_prefix is None:
                continue
            yield from route_paths(included.routes, prefix + nested_prefix)
            continue
        path = prefix + getattr(route, "path", "")
        if not path:
            continue
        yield RoutePath(
            path,
            compile_path(path)[0],
            getattr(route, "name", None),
            frozenset(getattr(route, "methods", ()) or ()),
            isinstance(route, Mount),
        )


def check_reserved_routes(
    routes: Iterable[RoutePath], static: str, health: str, name: str
) -> None:
    for route in routes:
        if (
            route.name in (name, "app-factory-health")
            or route.path == health
            or route.path == static
            or route.path.startswith(static + "/")
            or route.regex.fullmatch(health)
            or route.regex.fullmatch(static + "/file.css")
            or (
                route.mount
                and (
                    health.startswith(route.path + "/")
                    or static.startswith(route.path + "/")
                )
            )
        ):
            raise ValueError(f"product host path/mount conflict: {route.path!r}")


def check_domain_routes(
    domain: Iterable[RoutePath], installed: Iterable[RoutePath]
) -> None:
    existing = list(installed)
    for route in domain:
        for other in existing:
            overlap = (
                route.path == other.path
                or other.regex.fullmatch(route.path)
                or route.regex.fullmatch(other.path)
                or (other.mount and route.path.startswith(other.path + "/"))
            )
            if overlap and (
                not route.methods or not other.methods or route.methods & other.methods
            ):
                raise ValueError(f"product host route conflict: {route.path!r}")
        existing.append(route)


def _error_fragment(request: Request, status: int, detail: str, headers=None):
    if request.headers.get("HX-Request", "").lower() != "true":
        return None
    return HTMLResponse(
        '<div class="alert" data-variant="destructive" role="alert">'
        f"{escape(detail)}</div>",
        status_code=status,
        headers=headers,
    )


async def product_http_error(request: Request, exc: HTTPException):
    if exc.status_code >= 400:
        fragment = _error_fragment(
            request, exc.status_code, str(exc.detail), exc.headers
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


def install_product_host(
    app: FastAPI,
    config: ProductAppConfig,
    *,
    routers: Iterable[APIRouter] = (),
    current_user: CurrentUser | None = None,
    locales: PageLocales | None = None,
    passkey: PasskeyBinding | None = None,
    usermanager: UserManagerBinding | None = None,
) -> ProductInstall:
    """Install before startup. Compatible repeats are no-ops.

    ``PlatformPaths.root`` is a route prefix (including domain routers), matching
    the identity adapters; do not also set FastAPI's ASGI ``root_path``.
    """
    routers = tuple(routers)
    signature = (
        config,
        tuple(id(router) for router in routers),
        current_user,
        locales,
        passkey,
        usermanager,
    )
    existing = getattr(app.state, "app_factory_product", None)
    if existing is not None:
        if app.state.app_factory_product_signature != signature:
            raise ValueError(
                "product host already installed with different configuration"
            )
        return existing
    if app.middleware_stack is not None:
        raise ValueError("install product host before application startup")
    if app.root_path:
        raise ValueError(
            "root_path conflicts with product host; use PlatformPaths.root"
        )
    for name in ("app_factory_ui", "app_factory_platform", "app_factory_identity"):
        if hasattr(app.state, name):
            raise ValueError(
                f"product host conflicts with existing {name} installation"
            )
    for key, default in (
        (HTTPException, http_exception_handler),
        (RequestValidationError, request_validation_exception_handler),
        (Exception, None),
        (500, None),
    ):
        if app.exception_handlers.get(key) not in (None, default):
            raise ValueError(f"product host error handler conflict: {key}")
    if passkey is not None and (passkey.service is None or passkey.hooks is None):
        raise ValueError("passkey.service and passkey.hooks must both be provided")
    if usermanager is not None:
        um_config = usermanager.ui_config or usermanager
        if um_config.admin_enabled and um_config.csrf_protection is None:
            raise ValueError(
                "csrf_protection is required when usermanager admin is enabled"
            )
    root = config.platform.paths.root.rstrip("/")
    static_path = join_platform_root(root, config.static_path.rstrip("/"))
    health_path = join_platform_root(root, config.health_path)
    if config.static_path == "/" or not config.mount_name:
        raise ValueError("static_path must be non-root; mount_name is required")
    if health_path == static_path or health_path.startswith(static_path + "/"):
        raise ValueError("health path conflicts with static mount")
    domain = APIRouter()
    for router in routers:
        domain.include_router(router, prefix=root)
    check_reserved_routes(
        route_paths([*app.routes, *domain.routes]),
        static_path,
        health_path,
        config.mount_name,
    )
    check_domain_routes(route_paths(domain.routes), route_paths(app.routes))
    environment = Jinja2Templates(directory=config.template_directory).env
    previous_routes = {id(route) for route in app.routes}
    identity = None
    if passkey is not None or usermanager is not None:
        if usermanager is not None and usermanager.environment is None:
            usermanager = replace(usermanager, environment=environment)
        identity = install_identity_adapters(
            app,
            environments=[environment],
            config=config.platform,
            static_path=static_path,
            mount_name=config.mount_name,
            passkey=passkey,
            usermanager=usermanager,
            current_user=current_user,
            locales=locales,
        )
        platform = identity.platform
        check_reserved_routes(
            (
                route
                for route in route_paths(
                    r for r in app.routes if id(r) not in previous_routes
                )
                if route.name != config.mount_name
            ),
            static_path,
            health_path,
            config.mount_name,
        )
        # Adapter template setup can reconfigure a supplied environment and reset
        # the URL helper. Restore the install-bound prefix after composition.
        for env in (
            environment,
            getattr(identity.passkey_ui, "environment", None),
            usermanager.environment if usermanager is not None else None,
        ):
            if env is not None:
                env.globals["platform_asset_prefix"] = platform.ui.asset_prefix
                env.globals["platform_asset_url"] = partial(
                    platform_asset_url, prefix=platform.ui.asset_prefix
                )
    else:
        platform = install_platform(
            app,
            environments=[environment],
            config=config.platform,
            static_path=static_path,
            mount_name=config.mount_name,
        )
    # The identity composer only installs context when callbacks are supplied.
    if identity is None or (current_user is None and locales is None):
        install_platform_request_context(
            app,
            config=config.platform,
            environments=[environment],
            current_user=current_user,
            locales=locales,
        )
    app.add_exception_handler(HTTPException, product_http_error)
    app.add_exception_handler(RequestValidationError, product_validation_error)
    app.add_exception_handler(Exception, product_server_error)
    app.add_middleware(
        SameOriginCsrfMiddleware,
        trusted_origins=config.csrf_trusted_origins,
        exempt_prefixes=config.csrf_exempt_prefixes,
    )
    # Adapter-owned paths are only known after their installers run. Do not
    # silently shadow them with a domain route (or an existing host route).
    check_domain_routes(route_paths(domain.routes), route_paths(app.routes))
    app.include_router(domain)

    @app.get(health_path, name="app-factory-health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    installed = ProductInstall(environment, platform, identity)
    app.state.app_factory_product = installed
    app.state.app_factory_product_signature = signature
    return installed


def create_product_app(
    config: ProductAppConfig,
    *,
    routers: Iterable[APIRouter] = (),
    lifespan: Lifespan[FastAPI] | None = None,
    current_user: CurrentUser | None = None,
    locales: PageLocales | None = None,
    passkey: PasskeyBinding | None = None,
    usermanager: UserManagerBinding | None = None,
) -> FastAPI:
    """Create a host; inject ordinary domain APIRouters, not factory storage."""
    app = FastAPI(title=config.platform.app_name, docs_url=None, lifespan=lifespan)
    install_product_host(
        app,
        config,
        routers=routers,
        current_user=current_user,
        locales=locales,
        passkey=passkey,
        usermanager=usermanager,
    )
    return app
