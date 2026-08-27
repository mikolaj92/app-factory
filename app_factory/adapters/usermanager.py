"""Install packaged my-usermanager UI on identity-authenticated chrome."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from jinja2 import Environment

from app_factory.adapters.paths import usermanager_config_from_platform
from app_factory.fastapi import AppFactoryUi
from app_factory.platform import IDENTITY_AUTHENTICATED_SHELL, PlatformPaths

__all__ = [
    "install_usermanager_adapter",
    "usermanager_config_from_platform",
]


def install_usermanager_adapter(
    app: FastAPI,
    *,
    platform: AppFactoryUi,
    hooks: Any,
    config: Any | None = None,
    environment: Environment | None = None,
    paths: PlatformPaths | None = None,
    csrf_protection: Any | None = None,
    account_enabled: bool = True,
    admin_enabled: bool = True,
    labels: dict[str, str] | None = None,
    base_template: str = IDENTITY_AUTHENTICATED_SHELL,
) -> Any:
    """Mount account/admin UI; default shell is the shared identity frame.

    Hosts keep RBAC catalogs and persistence hooks. CSRF is required when
    admin mutations are enabled — missing protection fails closed here
    before the adapter installer runs.
    """
    try:
        from my_usermanager.adapters.fastapi_htmx import install_usermanager_ui
    except ImportError as exc:
        raise ImportError(
            "install_usermanager_adapter requires my-usermanager[fastapi-htmx]"
        ) from exc

    selected = config
    if selected is None:
        if paths is None:
            raise ValueError(
                "usermanager adapter requires config= or paths= to derive routes"
            )
        if admin_enabled and csrf_protection is None:
            raise ValueError(
                "csrf_protection is required when usermanager admin is enabled"
            )
        selected = usermanager_config_from_platform(
            paths,
            csrf_protection=csrf_protection,
            account_enabled=account_enabled,
            admin_enabled=admin_enabled,
            labels=labels,
            base_template=base_template,
        )
    elif admin_enabled and getattr(selected, "admin_enabled", True):
        if getattr(selected, "csrf_protection", None) is None:
            raise ValueError(
                "csrf_protection is required when usermanager admin is enabled"
            )

    return install_usermanager_ui(
        app,
        platform=platform,
        hooks=hooks,
        config=selected,
        environment=environment,
    )
