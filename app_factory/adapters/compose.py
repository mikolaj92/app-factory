"""Compose chrome + passkey + usermanager installers once per app."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from jinja2 import Environment

from app_factory.adapters.passkey import (
    default_passkey_ui_config,
    install_passkey_adapter,
    passkey_paths_from_platform,
)
from app_factory.adapters.session import (
    attach_platform_page_context,
    install_platform_request_context,
)
from app_factory.adapters.usermanager import install_usermanager_adapter
from app_factory.platform import (
    IDENTITY_AUTHENTICATED_SHELL,
    PlatformConfig,
    PlatformInstall,
    PlatformLocale,
    PlatformUser,
    install_platform,
)

__all__ = [
    "IdentityAdapterConflict",
    "IdentityInstall",
    "PasskeyBinding",
    "UserManagerBinding",
    "install_identity_adapters",
]


class IdentityAdapterConflict(ValueError):
    """The application already composed identity adapters differently."""


@dataclass(frozen=True, slots=True)
class PasskeyBinding:
    """Host persistence + policy for packaged passkey UI.

    Supply ``service`` and session/registration hooks. Do not copy
    ``render_login`` / ``render_register`` — those stay in my-auth.
    """

    service: Any
    hooks: Any
    cookies: Any | None = None
    csrf_token: Callable[..., Any] | None = None
    csrf_header_name: str = "X-CSRF-Token"
    login_success_url: str | None = "/"
    register_success_url: str | None = "/"
    activation_success_url: str | None = "/account"
    recovery_success_url: str | None = "/login"
    show_registration_link: Callable[..., Any] | None = None
    locale_cookie_name: str | None = None
    locale_query_param: str = "lang"
    supported_locales: tuple[str, ...] | None = None
    default_locale: str | None = None
    ui_config: Any | None = None


@dataclass(frozen=True, slots=True)
class UserManagerBinding:
    """Host RBAC / persistence hooks for packaged account and admin UI."""

    hooks: Any
    csrf_protection: Any | None = None
    environment: Environment | None = None
    labels: Mapping[str, str] | None = None
    account_enabled: bool = True
    admin_enabled: bool = True
    base_template: str = IDENTITY_AUTHENTICATED_SHELL
    ui_config: Any | None = None


@dataclass(frozen=True, slots=True)
class IdentityInstall:
    """Result of :func:`install_identity_adapters`."""

    platform: PlatformInstall
    passkey_ui: Any | None = None
    usermanager_ui: Any | None = None


def install_identity_adapters(
    app: FastAPI,
    *,
    environments: Iterable[Environment],
    config: PlatformConfig | None = None,
    passkey: PasskeyBinding | None = None,
    usermanager: UserManagerBinding | None = None,
    current_user: Callable[[Request], PlatformUser | None] | None = None,
    locales: Callable[
        [Request], tuple[Sequence[PlatformLocale] | None, str | None]
    ]
    | None = None,
    static_path: str = "/static/platform",
    mount_name: str = "app-factory-platform",
) -> IdentityInstall:
    """Install chrome and both identity adapters without host installer forks.

    Idempotent for the same chrome + adapter selection. A second call with a
    different mount, config, or adapter set raises
    :class:`IdentityAdapterConflict`. Missing passkey hook/service pairs and
    admin UI without CSRF fail closed.
    """
    resolved = config or PlatformConfig()
    env_list = list(environments)
    signature = (
        resolved,
        passkey is not None,
        usermanager is not None,
        static_path.rstrip("/"),
        mount_name,
    )
    existing = getattr(app.state, "app_factory_identity", None)
    if existing is not None:
        previous = getattr(app.state, "app_factory_identity_signature", None)
        if previous != signature:
            raise IdentityAdapterConflict(
                "identity adapters already installed with different configuration"
            )
        return existing  # type: ignore[no-any-return]

    if passkey is not None and (passkey.service is None or passkey.hooks is None):
        raise ValueError(
            "passkey.service and passkey.hooks must both be provided to "
            "install passkey UI"
        )
    if (
        usermanager is not None
        and usermanager.admin_enabled
        and usermanager.ui_config is None
        and usermanager.csrf_protection is None
    ):
        raise ValueError(
            "csrf_protection is required when usermanager admin is enabled"
        )

    platform = install_platform(
        app,
        environments=env_list,
        config=resolved,
        static_path=static_path,
        mount_name=mount_name,
    )

    passkey_ui = None
    if passkey is not None:
        ui_config = passkey.ui_config
        if ui_config is None:
            ui_config = default_passkey_ui_config(
                passkey_paths_from_platform(resolved.paths),
                cookies=passkey.cookies,
                csrf_token=passkey.csrf_token,
                csrf_header_name=passkey.csrf_header_name,
                login_success_url=passkey.login_success_url,
                register_success_url=passkey.register_success_url,
                activation_success_url=_rooted_success_url(
                    resolved, passkey.activation_success_url, "account"
                ),
                recovery_success_url=_rooted_success_url(
                    resolved, passkey.recovery_success_url, "login"
                ),
                show_registration_link=passkey.show_registration_link,
                locale_cookie_name=passkey.locale_cookie_name,
                locale_query_param=passkey.locale_query_param,
                supported_locales=passkey.supported_locales,
                default_locale=passkey.default_locale,
            )
        passkey_ui = install_passkey_adapter(
            app,
            platform=platform.ui,
            service=passkey.service,
            hooks=passkey.hooks,
            config=ui_config,
            platform_config=resolved,
        )
        platform = PlatformInstall(
            ui=platform.ui, config=resolved, passkey_ui=passkey_ui
        )
        app.state.app_factory_platform = platform

    usermanager_ui = None
    if usermanager is not None:
        um_hooks = attach_platform_page_context(
            usermanager.hooks,
            config=resolved,
            current_user=current_user,
            locales=locales,
        )
        usermanager_ui = install_usermanager_adapter(
            app,
            platform=platform.ui,
            hooks=um_hooks,
            config=usermanager.ui_config,
            environment=usermanager.environment,
            paths=resolved.paths,
            csrf_protection=usermanager.csrf_protection,
            account_enabled=usermanager.account_enabled,
            admin_enabled=usermanager.admin_enabled,
            labels=dict(usermanager.labels) if usermanager.labels else None,
            base_template=usermanager.base_template,
        )

    request_environments = list(env_list)
    if passkey_ui is not None:
        environment = getattr(passkey_ui, "environment", None)
        if environment is not None and environment not in request_environments:
            request_environments.append(environment)
    if current_user is not None or locales is not None:
        install_platform_request_context(
            app,
            config=resolved,
            environments=request_environments,
            current_user=current_user,
            locales=locales,
        )

    installed = IdentityInstall(
        platform=platform,
        passkey_ui=passkey_ui,
        usermanager_ui=usermanager_ui,
    )
    app.state.app_factory_identity = installed
    app.state.app_factory_identity_signature = signature
    return installed


def _rooted_success_url(
    config: PlatformConfig, supplied: str | None, surface: str
) -> str | None:
    """Keep host overrides; default identity surfaces follow ``PlatformPaths``."""
    if supplied is None:
        return None
    defaults = {"account": "/account", "login": "/login"}
    if supplied == defaults.get(surface) and config.paths.root:
        return config.paths.href(surface)
    return supplied
