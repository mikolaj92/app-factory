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
    from app_factory.fastapi import (
        AppFactoryUi,
        AppFactoryUiConflict,
        install_app_factory_ui,
    )
except ImportError:  # Optional fastapi extra is not installed.
    AppFactoryUi = AppFactoryUiConflict = install_app_factory_ui = None

__all__ = [
    "CDN_ASSET_MANIFEST",
    "AppFactoryUi",
    "AppFactoryUiConflict",
    "BundledAsset",
    "CDNAsset",
    "CDNVerificationError",
    "bundled_asset",
    "cdn_asset",
    "configure_jinja_env",
    "extend_manifest",
    "factory_template_dirs",
    "get_assets_dir",
    "get_platform_static_app",
    "install_app_factory_ui",
    "list_bundled_assets",
    "platform_asset_url",
    "verify_cdn_asset",
    "verify_cdn_manifest",
]

__version__ = "0.4.1"
