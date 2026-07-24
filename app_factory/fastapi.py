"""One FastAPI mount for app-factory's shared frontend assets."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from typing import Any

from app_factory.assets import get_platform_static_app, platform_asset_url
from app_factory.jinja import configure_jinja_env
try:
    from fastapi import FastAPI
    from jinja2 import Environment
except ImportError as exc:
    raise ImportError(
        "app_factory.fastapi requires app-factory[fastapi]"
    ) from exc


class AppFactoryUiConflict(ValueError):
    """The application already uses a different platform mount."""


@dataclass(frozen=True, slots=True)
class AppFactoryUi:
    static_path: str
    mount_name: str
    asset_prefix: str


def install_app_factory_ui(
    app: FastAPI,
    *,
    environments: Iterable[Environment],
    static_path: str = "/static/platform",
    mount_name: str = "app-factory-platform",
) -> AppFactoryUi:
    """Mount shared assets once and configure each supplied Jinja environment."""
    static_path = static_path.rstrip("/")
    if not static_path.startswith("/") or static_path == "/" or not mount_name:
        raise ValueError("static_path must be an absolute non-root path; mount_name is required")

    requested = AppFactoryUi(
        static_path=static_path,
        mount_name=mount_name,
        asset_prefix=static_path,
    )
    installed = getattr(app.state, "app_factory_ui", None)
    if installed is not None and installed != requested:
        raise AppFactoryUiConflict(
            f"app-factory UI already installed at {installed.static_path!r} "
            f"as {installed.mount_name!r}"
        )

    if installed is None:
        app.mount(static_path, get_platform_static_app(), name=mount_name)
        app.state.app_factory_ui = requested

    configured = getattr(app.state, "app_factory_jinja_environments", set())
    for environment in environments:
        if id(environment) in configured:
            continue
        configure_jinja_env(environment)
        environment.globals["platform_asset_prefix"] = requested.asset_prefix
        environment.globals["platform_asset_url"] = partial(
            platform_asset_url, prefix=requested.asset_prefix
        )
        configured.add(id(environment))
    app.state.app_factory_jinja_environments = configured
    return requested
