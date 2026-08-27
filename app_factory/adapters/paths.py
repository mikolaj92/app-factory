"""Map :class:`~app_factory.platform.PlatformPaths` onto adapter path objects."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app_factory.platform import IDENTITY_AUTHENTICATED_SHELL, PlatformPaths, join_platform_root

# User-manager mutation/list surfaces that are not identity-nav slots.
# GET invite lives on the users list; POST stays on this path.
_USERMANAGER_DEFAULT_PATHS: Mapping[str, str] = {
    "account_path": "/account",
    "profile_path": "/account/profile",
    "users_path": "/admin/users",
    "disable_user_path": "/admin/users/disable",
    "enable_user_path": "/admin/users/enable",
    "grant_role_path": "/admin/users/grant-role",
    "revoke_role_path": "/admin/users/revoke-role",
    "grant_permission_path": "/admin/users/grant-permission",
    "revoke_permission_path": "/admin/users/revoke-permission",
    "invite_path": "/admin/users/invite",
    "reissue_invitation_path": "/admin/users/invitations/reissue",
    "revoke_invitation_path": "/admin/users/invitations/revoke",
    "soft_delete_user_path": "/admin/users/delete",
    "hard_delete_user_path": "/admin/users/delete-permanently",
    "sessions_path": "/account/sessions",
    "revoke_session_path": "/account/sessions/revoke",
    "audit_path": "/admin/audit",
}


def rooted_adapter_path(paths: PlatformPaths, path: str) -> str:
    """Prefix an adapter-owned absolute path with ``PlatformPaths.root``."""
    return join_platform_root(paths.root, path)


def passkey_paths_from_platform(paths: PlatformPaths) -> Any:
    """Build my-auth ``PasskeyPaths`` aligned with the platform contract."""
    try:
        from my_auth.fastapi import PasskeyPaths
    except ImportError as exc:
        raise ImportError(
            "passkey_paths_from_platform requires my-auth[fastapi-htmx]"
        ) from exc

    defaults = PasskeyPaths()
    resolved = paths.resolved()
    return PasskeyPaths(
        login_page=resolved.login,
        register_page=resolved.register,
        activation_page=resolved.activation,
        recovery_page=resolved.recovery,
        credentials_page=resolved.credentials,
        logout=resolved.logout,
        credential_label=rooted_adapter_path(paths, defaults.credential_label),
        credential_remove=rooted_adapter_path(paths, defaults.credential_remove),
        login_options=rooted_adapter_path(paths, defaults.login_options),
        login_verify=rooted_adapter_path(paths, defaults.login_verify),
        register_options=rooted_adapter_path(paths, defaults.register_options),
        register_verify=rooted_adapter_path(paths, defaults.register_verify),
    )


def usermanager_path_kwargs(paths: PlatformPaths) -> dict[str, str]:
    """Rooted usermanager route fields, including mutation POST paths."""
    resolved = paths.resolved()
    kwargs = {
        name: rooted_adapter_path(paths, default)
        for name, default in _USERMANAGER_DEFAULT_PATHS.items()
    }
    kwargs["account_path"] = resolved.account
    kwargs["users_path"] = resolved.admin_users
    kwargs["login_url"] = resolved.login
    kwargs["logout_path"] = resolved.logout
    return kwargs


def usermanager_config_from_platform(
    paths: PlatformPaths,
    *,
    csrf_protection: Any | None = None,
    account_enabled: bool = True,
    admin_enabled: bool = True,
    labels: Mapping[str, str] | None = None,
    base_template: str = IDENTITY_AUTHENTICATED_SHELL,
    **overrides: Any,
) -> Any:
    """Build my-usermanager ``UserManagerUiConfig`` from platform paths."""
    try:
        from my_usermanager.adapters.fastapi_htmx import UserManagerUiConfig
    except ImportError as exc:
        raise ImportError(
            "usermanager_config_from_platform requires "
            "my-usermanager[fastapi-htmx]"
        ) from exc

    kwargs: dict[str, Any] = {
        **usermanager_path_kwargs(paths),
        "csrf_protection": csrf_protection,
        "account_enabled": account_enabled,
        "admin_enabled": admin_enabled,
        "base_template": base_template,
    }
    if labels is not None:
        kwargs["labels"] = labels
    kwargs.update(overrides)
    return UserManagerUiConfig(**kwargs)
