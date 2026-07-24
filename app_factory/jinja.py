"""Jinja helpers for bundled core assets and optional CDN extras."""

from importlib.resources import files
from pathlib import Path
from typing import cast

from jinja2 import (
    BaseLoader,
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
)

from app_factory.assets import bundled_asset, list_bundled_assets, platform_asset_url
from app_factory.cdn import CDN_ASSET_MANIFEST, cdn_asset


def factory_template_dirs() -> list[Path]:
    """Directories of package-shipped Jinja partials (``app_factory/...``)."""
    root = files("app_factory").joinpath("templates")
    return [Path(str(root))]


def configure_jinja_env(
    env: Environment, *, include_factory_templates: bool = True
) -> Environment:
    """Register bundled core assets, CDN extras, and the template loader.
    When ``include_factory_templates`` is true, prepends factory template dirs
    so hosts can ``{% include "app_factory/head_assets.html" %}``.
    """
    globals_dict = cast(dict[str, object], env.globals)
    globals_dict["bundled_asset"] = bundled_asset
    globals_dict["bundled_assets"] = tuple(list_bundled_assets())
    globals_dict["platform_asset_url"] = platform_asset_url
    globals_dict["cdn_asset"] = cdn_asset
    globals_dict["cdn_assets"] = CDN_ASSET_MANIFEST

    if include_factory_templates:
        loaders: list[BaseLoader] = []
        # Prefer package loader so installed wheels work
        try:
            loaders.append(PackageLoader("app_factory", "templates"))
        except (ImportError, OSError, ValueError):
            for directory in factory_template_dirs():
                if directory.is_dir():
                    loaders.append(FileSystemLoader(str(directory)))

        if loaders:
            existing = env.loader
            if existing is not None:
                env.loader = ChoiceLoader([existing, *loaders])
            else:
                env.loader = ChoiceLoader(loaders)
    return env
