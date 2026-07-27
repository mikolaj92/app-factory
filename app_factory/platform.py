"""Platform composition: shared chrome + optional passkey UI wiring.

Hosts call :func:`install_platform` once instead of re-copying shell, theme boot,
and auth foot across apps. Domain menu items are host-supplied; the platform
foot (locale / theme / login / account / logout) is fixed. Hosts must not put
those controls in the main header.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Callable

from jinja2 import Environment

from app_factory.fastapi import AppFactoryUi, install_app_factory_ui

try:
    from fastapi import FastAPI
except ImportError as exc:  # pragma: no cover
    raise ImportError("app_factory.platform requires app-factory[fastapi]") from exc


@dataclass(frozen=True, slots=True)
class MenuItem:
    """One host navigation entry in the shared product sidebar."""

    label: str
    href: str
    icon: str | None = None
    active: bool = False
    no_htmx: bool = False


@dataclass(frozen=True, slots=True)
class PlatformLocale:
    """One language option for the shared platform foot.

    Prefer ``href`` for server-side locale switching (query/cookie). Omit
    ``href`` for client-side apps: the foot emits a button with
    ``data-platform-locale-select`` and ``data-locale`` so the host can
    handle ``platform:locale`` (see theme_boot) or bind its own listener.
    """

    code: str
    label: str
    href: str | None = None


@dataclass(frozen=True, slots=True)
class PlatformPaths:
    """Canonical auth/account URLs used by the shared platform foot."""

    login: str = "/login"
    logout: str = "/logout"
    register: str = "/register"
    account: str = "/account"
    admin_users: str = "/admin/users"


@dataclass(frozen=True, slots=True)
class PlatformUser:
    """Minimal user view for shell templates (host maps session → this)."""

    display_name: str
    is_admin: bool = False
    user_id: str | None = None


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """Host-visible platform chrome configuration."""

    app_name: str = "App"
    menu: tuple[MenuItem, ...] = ()
    paths: PlatformPaths = field(default_factory=PlatformPaths)
    enable_admin_users: bool = False
    show_register: bool = True
    # Static default locales (usually empty; per-request hrefs go via
    # build_platform_context(..., locales=...)).
    locales: tuple[PlatformLocale, ...] = ()
    default_locale: str | None = None


@dataclass(frozen=True, slots=True)
class PlatformInstall:
    """Result of :func:`install_platform`."""

    ui: AppFactoryUi
    config: PlatformConfig
    passkey_ui: Any | None = None


def build_platform_context(
    config: PlatformConfig,
    *,
    user: PlatformUser | None = None,
    current_path: str = "",
    locales: Sequence[PlatformLocale] | None = None,
    locale: str | None = None,
) -> dict[str, Any]:
    """Build Jinja globals/context for product shell + platform foot.

    Pure function — safe for unit tests without FastAPI or WebAuthn.

    ``locales`` / ``locale`` override config defaults so hosts can inject
    per-request language links (e.g. preserve query on the current path).
    """
    menu = tuple(
        MenuItem(
            label=item.label,
            href=item.href,
            icon=item.icon,
            active=item.active or _path_active(current_path, item.href),
            no_htmx=item.no_htmx,
        )
        for item in config.menu
    )
    resolved_locales = tuple(locales) if locales is not None else config.locales
    resolved_locale = locale if locale is not None else config.default_locale
    return {
        "app_name": config.app_name,
        "platform_menu": menu,
        "platform_user": user,
        "platform_paths": config.paths,
        "platform_enable_admin_users": config.enable_admin_users,
        "platform_show_register": config.show_register,
        "platform_locales": resolved_locales,
        "platform_locale": resolved_locale,
        "login_url": config.paths.login,
    }


def _path_active(current_path: str, href: str) -> bool:
    if not current_path or not href:
        return False
    if current_path == href:
        return True
    if href != "/" and current_path.startswith(href.rstrip("/") + "/"):
        return True
    return False


def apply_platform_context(
    environment: Environment,
    config: PlatformConfig,
    *,
    user: PlatformUser | None = None,
    current_path: str = "",
    locales: Sequence[PlatformLocale] | None = None,
    locale: str | None = None,
) -> Mapping[str, Any]:
    """Merge platform context into a Jinja environment's globals."""
    ctx = build_platform_context(
        config,
        user=user,
        current_path=current_path,
        locales=locales,
        locale=locale,
    )
    globals_dict = environment.globals
    globals_dict.update(ctx)
    return ctx


def install_platform(
    app: FastAPI,
    *,
    environments: Iterable[Environment],
    config: PlatformConfig | None = None,
    passkey_service: Any | None = None,
    passkey_hooks: Any | None = None,
    passkey_config: Any | None = None,
    usermanager_installer: Callable[[FastAPI, AppFactoryUi], Any] | None = None,
    static_path: str = "/static/platform",
    mount_name: str = "app-factory-platform",
) -> PlatformInstall:
    """Install shared chrome and optionally wire my-auth passkey UI.

    When ``passkey_service`` and ``passkey_hooks`` are provided, requires the
    ``platform`` (or at least ``my-auth[fastapi-htmx]``) extra and mounts the
    packaged passkey routes. Hosts still supply session hooks; they do not
    re-copy login templates or theme boot.
    """
    resolved = config or PlatformConfig()
    env_list = list(environments)
    ui = install_app_factory_ui(
        app,
        environments=env_list,
        static_path=static_path,
        mount_name=mount_name,
    )
    for environment in env_list:
        apply_platform_context(environment, resolved)

    passkey_ui = None
    if passkey_service is not None or passkey_hooks is not None:
        if passkey_service is None or passkey_hooks is None:
            raise ValueError(
                "passkey_service and passkey_hooks must both be provided to "
                "install passkey UI"
            )
        try:
            from my_auth.fastapi_htmx import install_passkey_ui
        except ImportError as exc:
            raise ImportError(
                "install_platform passkey wiring requires my-auth[fastapi-htmx] "
                "(install app-factory[platform])"
            ) from exc
        passkey_ui = install_passkey_ui(
            app,
            platform=ui,
            service=passkey_service,
            hooks=passkey_hooks,
            config=passkey_config,
        )
        app.include_router(passkey_ui.router)

    if usermanager_installer is not None:
        usermanager_installer(app, ui)

    app.state.app_factory_platform = PlatformInstall(
        ui=ui, config=resolved, passkey_ui=passkey_ui
    )
    return app.state.app_factory_platform


# Classes forbidden in platform-shipped templates (Basecoat 1.0 contract).
FORBIDDEN_BASECOAT_CLASS_MARKERS: tuple[str, ...] = (
    "btn-primary",
    "btn-secondary",
    "btn-destructive",
    "btn-ghost",
    "card-header",
    "card-content",
)
