"""Shared frontend chrome for FastAPI + Jinja + HTMX + basecoat-factory apps."""

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

__all__ = [
    "BundledAsset",
    "bundled_asset",
    "get_assets_dir",
    "get_platform_static_app",
    "list_bundled_assets",
    "platform_asset_url",
    "CDN_ASSET_MANIFEST",
    "CDNAsset",
    "CDNVerificationError",
    "cdn_asset",
    "configure_jinja_env",
    "extend_manifest",
    "factory_template_dirs",
    "verify_cdn_asset",
    "verify_cdn_manifest",
]

__version__ = "0.3.0"
