"""Per-request product-shell context for adapter and host environments."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any

from fastapi import FastAPI, Request
from jinja2 import Environment

from app_factory.platform import (
    PlatformConfig,
    PlatformLocale,
    PlatformUser,
    build_platform_context,
)

CurrentUser = Callable[[Request], PlatformUser | None]
PageLocales = Callable[
    [Request], tuple[Sequence[PlatformLocale] | None, str | None]
]


def attach_platform_page_context(
    hooks: Any,
    *,
    config: PlatformConfig,
    current_user: CurrentUser | None = None,
    locales: PageLocales | None = None,
) -> Any:
    """Delegate UM hooks and supply ``page_context`` when the host omitted it.

    Hosts that already implement ``page_context`` keep that method. Product
    copy and extra template keys stay host-owned.
    """
    if getattr(hooks, "page_context", None) is not None:
        return hooks
    return _DerivedPageContext(hooks, config, current_user, locales)


class _DerivedPageContext:
    """Proxy that adds platform ``page_context`` onto host policy hooks."""

    def __init__(
        self,
        hooks: Any,
        config: PlatformConfig,
        current_user: CurrentUser | None,
        locales: PageLocales | None,
    ) -> None:
        self._hooks = hooks
        self._config = config
        self._current_user = current_user
        self._locales = locales

    def page_context(self, request: Request) -> dict[str, Any]:
        user = self._current_user(request) if self._current_user else None
        locale_args: dict[str, Any] = {}
        if self._locales is not None:
            resolved_locales, locale = self._locales(request)
            locale_args["locales"] = resolved_locales
            locale_args["locale"] = locale
        return dict(
            build_platform_context(
                self._config,
                user=user,
                current_path=request.url.path,
                **locale_args,
            )
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._hooks, name)


def install_platform_request_context(
    app: FastAPI,
    *,
    config: PlatformConfig,
    environments: Iterable[Environment],
    current_user: CurrentUser | None = None,
    locales: PageLocales | None = None,
) -> None:
    """Expose request-local platform chrome context on ``request.state``.

    ``environments`` remains accepted for API compatibility, but request data is
    never written to shared Jinja ``Environment.globals``. Renderers merge
    ``request.state.app_factory_platform_context`` into each template response.

    Add host ``SessionMiddleware`` *after* this installer (Starlette runs the
    last-added middleware first) so the session is available when
    ``current_user`` reads it.
    """
    _ = tuple(environments)

    @app.middleware("http")
    async def bind_platform_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        user = current_user(request) if current_user is not None else None
        locale_args: dict[str, Any] = {}
        if locales is not None:
            resolved_locales, locale = locales(request)
            locale_args["locales"] = resolved_locales
            locale_args["locale"] = locale
        request.state.app_factory_platform_context = dict(
            build_platform_context(
                config,
                user=user,
                current_path=request.url.path,
                **locale_args,
            )
        )
        return await call_next(request)
