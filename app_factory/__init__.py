"""Shared frontend chrome for FastAPI + Jinja + HTMX + Basecoat UI apps."""

from app_factory.assets import (
    BundledAsset,
    bundled_asset,
    get_assets_dir,
    get_platform_static_app,
    list_bundled_assets,
    platform_asset_url,
)
from app_factory.cdn import (
    CDN_ASSET_MANIFEST,
    CDNAsset,
    CDNVerificationError,
    cdn_asset,
    extend_manifest,
    verify_cdn_asset,
    verify_cdn_manifest,
)
from app_factory.jinja import configure_jinja_env, factory_template_dirs

try:
    from app_factory.csrf import SessionCsrfProtection
    from app_factory.fastapi import (
        AppFactoryUi,
        AppFactoryUiConflict,
        install_app_factory_ui,
    )
    from app_factory.responses import htmx_redirect
except ImportError:  # Optional fastapi extra is not installed.
    AppFactoryUi = AppFactoryUiConflict = SessionCsrfProtection = None
    htmx_redirect = install_app_factory_ui = None

try:
    from app_factory.adapters import (
        IdentityAdapterConflict,
        IdentityInstall,
        PasskeyBinding,
        UserManagerBinding,
        attach_platform_page_context,
        complete_passkey_hooks,
        install_identity_adapters,
        install_passkey_adapter,
        install_platform_request_context,
        install_usermanager_adapter,
        passkey_paths_from_platform,
        usermanager_config_from_platform,
    )
    from app_factory.platform import (
        CLIENT_SHELL,
        IDENTITY_ADMIN_SURFACES,
        IDENTITY_AUTHENTICATED_SHELL,
        IDENTITY_AUTHENTICATED_SURFACES,
        IDENTITY_DENIED,
        IDENTITY_DENIED_FRAGMENT,
        IDENTITY_PUBLIC_SHELL,
        IDENTITY_PUBLIC_STATE,
        IDENTITY_PUBLIC_SURFACES,
        IDENTITY_SURFACES,
        MenuGroup,
        MenuItem,
        PlatformConfig,
        PlatformInstall,
        PlatformLocale,
        PlatformPaths,
        PlatformUser,
        apply_platform_context,
        build_platform_context,
        install_platform,
        join_platform_root,
    )
except ImportError:  # Optional fastapi extra is not installed.
    CLIENT_SHELL = None
    IDENTITY_ADMIN_SURFACES = IDENTITY_AUTHENTICATED_SURFACES = None
    IDENTITY_AUTHENTICATED_SHELL = IDENTITY_DENIED = IDENTITY_DENIED_FRAGMENT = None
    IDENTITY_PUBLIC_SHELL = IDENTITY_PUBLIC_STATE = None
    IDENTITY_PUBLIC_SURFACES = IDENTITY_SURFACES = None
    MenuGroup = MenuItem = PlatformConfig = PlatformInstall = None
    PlatformLocale = PlatformPaths = PlatformUser = None
    apply_platform_context = build_platform_context = install_platform = None
    join_platform_root = None
    IdentityAdapterConflict = IdentityInstall = None
    PasskeyBinding = UserManagerBinding = None
    attach_platform_page_context = complete_passkey_hooks = None
    install_identity_adapters = install_passkey_adapter = None
    install_platform_request_context = install_usermanager_adapter = None
    passkey_paths_from_platform = usermanager_config_from_platform = None

__all__ = [
    "CDN_ASSET_MANIFEST",
    "CLIENT_SHELL",
    "IDENTITY_ADMIN_SURFACES",
    "IDENTITY_AUTHENTICATED_SHELL",
    "IDENTITY_AUTHENTICATED_SURFACES",
    "IDENTITY_DENIED",
    "IDENTITY_DENIED_FRAGMENT",
    "IDENTITY_PUBLIC_SHELL",
    "IDENTITY_PUBLIC_STATE",
    "IDENTITY_PUBLIC_SURFACES",
    "IDENTITY_SURFACES",
    "AppFactoryUi",
    "AppFactoryUiConflict",
    "IdentityAdapterConflict",
    "IdentityInstall",
    "BundledAsset",
    "CDNAsset",
    "CDNVerificationError",
    "MenuGroup",
    "MenuItem",
    "PasskeyBinding",
    "PlatformConfig",
    "PlatformInstall",
    "PlatformLocale",
    "PlatformPaths",
    "PlatformUser",
    "SessionCsrfProtection",
    "UserManagerBinding",
    "apply_platform_context",
    "attach_platform_page_context",
    "build_platform_context",
    "bundled_asset",
    "cdn_asset",
    "complete_passkey_hooks",
    "configure_jinja_env",
    "extend_manifest",
    "factory_template_dirs",
    "get_assets_dir",
    "get_platform_static_app",
    "htmx_redirect",
    "install_app_factory_ui",
    "install_identity_adapters",
    "install_passkey_adapter",
    "install_platform",
    "install_platform_request_context",
    "install_usermanager_adapter",
    "join_platform_root",
    "passkey_paths_from_platform",
    "list_bundled_assets",
    "platform_asset_url",
    "usermanager_config_from_platform",
    "verify_cdn_asset",
    "verify_cdn_manifest",
]

__version__ = "0.6.12"
