"""Jinja helpers for bundled core assets and optional CDN extras."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

from app_factory.cdn import CDN_ASSET_MANIFEST, cdn_asset
from app_factory.assets import bundled_asset, list_bundled_assets, platform_asset_url


def factory_template_dirs() -> list[Path]:
    """Directories of package-shipped Jinja partials (``app_factory/...``)."""
    root = files("app_factory").joinpath("templates")
    return [Path(str(root))]


def configure_jinja_env(env: Any, *, include_factory_templates: bool = True) -> Any:
    """Register bundled core assets, CDN extras, and the template loader.
    When ``include_factory_templates`` is true, prepends factory template dirs
    so hosts can ``{% include "app_factory/head_assets.html" %}``.
    """
    env.globals["bundled_asset"] = bundled_asset
    env.globals["bundled_assets"] = tuple(list_bundled_assets())
    env.globals["platform_asset_url"] = platform_asset_url
    env.globals["cdn_asset"] = cdn_asset
    env.globals["cdn_assets"] = CDN_ASSET_MANIFEST

    if include_factory_templates:
        try:
            from jinja2 import ChoiceLoader, FileSystemLoader, PackageLoader
        except ImportError:
            return env

        loaders = []
        # Prefer package loader so installed wheels work
        try:
            loaders.append(PackageLoader("app_factory", "templates"))
        except Exception:
            for d in factory_template_dirs():
                if d.is_dir():
                    loaders.append(FileSystemLoader(str(d)))

        if loaders:
            existing = env.loader
            if existing is not None:
                from jinja2 import ChoiceLoader as CL

                env.loader = CL([existing, *loaders])
            else:
                from jinja2 import ChoiceLoader as CL

                env.loader = CL(loaders)
    return env
