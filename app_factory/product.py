"""Thin FastAPI host composition; persistence and product policy stay outside."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path
from functools import partial

from fastapi import APIRouter, FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from starlette.exceptions import HTTPException
from jinja2 import Environment
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
from app_factory.product_errors import (
    product_http_error,
    product_server_error,
    product_validation_error,
)
from app_factory.product_routes import (
    check_domain_routes,
    check_reserved_routes,
    route_paths,
)
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
    if not config.health_path.startswith("/") or config.health_path == "/":
        raise ValueError("health_path must be an absolute non-root path")
    if (
        not config.static_path.startswith("/")
        or config.static_path == "/"
        or not config.mount_name
    ):
        raise ValueError(
            "static_path must be an absolute non-root path; mount_name is required"
        )
    root = config.platform.paths.root.rstrip("/")
    static_path = join_platform_root(root, config.static_path.rstrip("/"))
    health_path = join_platform_root(root, config.health_path)
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
