"""Install packaged my-auth passkey UI without host render stubs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from app_factory.adapters.paths import passkey_paths_from_platform
from app_factory.fastapi import AppFactoryUi
from app_factory.platform import PlatformConfig, apply_platform_context

__all__ = [
    "complete_passkey_hooks",
    "install_passkey_adapter",
    "passkey_paths_from_platform",
]


def _unused_render_login(_request: Request) -> HTMLResponse:
    raise RuntimeError("interactive rendering is owned by my-auth.fastapi_htmx")


def _unused_render_register(_request: Request) -> HTMLResponse:
    raise RuntimeError("interactive rendering is owned by my-auth.fastapi_htmx")


def complete_passkey_hooks(hooks: Any) -> Any:
    """Fill ceremony-owned render slots so hosts omit dummy callables.

    Hosts still supply persistence and session policy
    (``get_session_user``, ``prepare_registration``, ``login``, …).
    ``install_passkey_ui`` replaces these stubs with packaged renderers.
    """
    try:
        from my_auth.fastapi import PasskeyRouteHooks
    except ImportError as exc:
        raise ImportError(
            "complete_passkey_hooks requires my-auth[fastapi-htmx]"
        ) from exc

    if type(hooks) is PasskeyRouteHooks:
        return hooks

    def _attr(name: str, default: Any) -> Any:
        return getattr(hooks, name, default)

    return PasskeyRouteHooks(
        get_session_user=hooks.get_session_user,
        prepare_registration=hooks.prepare_registration,
        complete_registration=hooks.complete_registration,
        get_auth_user=hooks.get_auth_user,
        login=hooks.login,
        logout=hooks.logout,
        render_login=_attr("render_login", _unused_render_login),
        render_register=_attr("render_register", _unused_render_register),
        after_register=_attr(
            "after_register", lambda _request, _user, _credential: None
        ),
        after_login=_attr("after_login", lambda _request, _user, _credential: None),
        prepare_registration_context=_attr("prepare_registration_context", None),
        prepare_capability_registration_context=_attr(
            "prepare_capability_registration_context", None
        ),
        render_capability_registration=_attr(
            "render_capability_registration", None
        ),
        render_credential_management=_attr("render_credential_management", None),
        allow_final_credential_removal=_attr(
            "allow_final_credential_removal", None
        ),
    )


def install_passkey_adapter(
    app: FastAPI,
    *,
    platform: AppFactoryUi,
    service: Any,
    hooks: Any,
    config: Any | None = None,
    platform_config: PlatformConfig | None = None,
    include_router: bool = False,
) -> Any:
    """Mount packaged passkey UI and bind platform chrome to its environment.

    ``install_passkey_ui`` (my-auth ≥ v0.4.5) already includes the router.
    Pass ``include_router=True`` only for older adapters that do not.
    """
    try:
        from my_auth.fastapi_htmx import install_passkey_ui
    except ImportError as exc:
        raise ImportError(
            "install_passkey_adapter requires my-auth[fastapi-htmx]"
        ) from exc

    passkey_ui = install_passkey_ui(
        app,
        platform=platform,
        service=service,
        hooks=complete_passkey_hooks(hooks),
        config=config,
    )
    environment = getattr(passkey_ui, "environment", None)
    if environment is not None and platform_config is not None:
        apply_platform_context(environment, platform_config)
    if include_router:
        app.include_router(passkey_ui.router)
    return passkey_ui


def default_passkey_ui_config(
    paths: Any,
    *,
    cookies: Any | None = None,
    csrf_token: Callable[..., Any] | None = None,
    csrf_header_name: str = "X-CSRF-Token",
    login_success_url: str | None = None,
    register_success_url: str | None = None,
    activation_success_url: str | None = None,
    recovery_success_url: str | None = None,
    locale_cookie_name: str | None = None,
    locale_query_param: str = "lang",
    supported_locales: tuple[str, ...] | None = None,
    default_locale: str | None = None,
) -> Any:
    """Build ``PasskeyUiConfig`` from already-aligned ``PasskeyPaths``."""
    try:
        from my_auth.fastapi import PasskeyCookies
        from my_auth.fastapi_htmx import PasskeyUiConfig
    except ImportError as exc:
        raise ImportError(
            "default_passkey_ui_config requires my-auth[fastapi-htmx]"
        ) from exc

    kwargs: dict[str, Any] = {
        "paths": paths,
        "cookies": cookies if cookies is not None else PasskeyCookies(),
        "csrf_header_name": csrf_header_name,
    }
    if csrf_token is not None:
        kwargs["csrf_token"] = csrf_token
    if login_success_url is not None:
        kwargs["login_success_url"] = login_success_url
    if register_success_url is not None:
        kwargs["register_success_url"] = register_success_url
    if activation_success_url is not None:
        kwargs["activation_success_url"] = activation_success_url
    if recovery_success_url is not None:
        kwargs["recovery_success_url"] = recovery_success_url
    if locale_cookie_name is not None:
        kwargs["locale_cookie_name"] = locale_cookie_name
    if locale_query_param != "lang":
        kwargs["locale_query_param"] = locale_query_param
    if supported_locales is not None:
        kwargs["supported_locales"] = supported_locales
    if default_locale is not None:
        kwargs["default_locale"] = default_locale
    return PasskeyUiConfig(**kwargs)
