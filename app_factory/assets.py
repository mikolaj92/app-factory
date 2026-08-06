"""Local bundled platform assets loaded from the generated package manifest."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from starlette.types import ASGIApp

AssetKind = Literal["script", "style", "font"]

_CORE_NAMES = {
    "alpine",
    "basecoat-css",
    "basecoat-js-all",
    "htmx",
    "material-symbols-css",
    "material-symbols-font",
}


@dataclass(frozen=True, slots=True)
class BundledAsset:
    """A core file shipped below ``app_factory/assets``."""

    name: str
    filename: str
    version: str
    integrity: str
    kind: AssetKind


@lru_cache(maxsize=1)
def _bundled_assets() -> dict[str, BundledAsset]:
    """Load and verify the sole generated manifest once per process."""
    root = files("app_factory").joinpath("assets")
    loaded = cast(
        object,
        json.loads(root.joinpath("MANIFEST.json").read_text(encoding="utf-8")),
    )
    if (
        not isinstance(loaded, dict)
        or set(cast(dict[str, object], loaded)) != _CORE_NAMES
    ):
        raise RuntimeError("invalid bundled asset manifest names")

    assets: dict[str, BundledAsset] = {}
    raw = cast(dict[str, object], loaded)
    for name, value in raw.items():
        if not isinstance(value, dict):
            raise TypeError("invalid bundled asset manifest entry")
        entry = cast(dict[str, object], value)
        filename = entry.get("filename")
        version = entry.get("version")
        integrity = entry.get("integrity")
        kind = entry.get("kind")
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or not isinstance(version, str)
            or not version
            or not isinstance(integrity, str)
            or not integrity.startswith("sha384-")
            or kind not in ("script", "style", "font")
        ):
            raise RuntimeError(f"invalid bundled asset manifest entry: {name}")
        resource = root.joinpath(filename)
        if not resource.is_file():
            raise RuntimeError(f"bundled asset is missing: {filename}")
        digest = "sha384-" + base64.b64encode(
            hashlib.sha384(resource.read_bytes()).digest()
        ).decode("ascii")
        if digest != integrity:
            raise RuntimeError(f"bundled asset integrity mismatch: {name}")
        assets[name] = BundledAsset(
            name=name,
            filename=filename,
            version=version,
            integrity=integrity,
            kind=kind,
        )
    return assets


def bundled_asset(name: str) -> BundledAsset:
    try:
        return _bundled_assets()[name]
    except KeyError as exc:
        raise KeyError(f"unknown bundled asset: {name}") from exc


def list_bundled_assets() -> Iterable[BundledAsset]:
    return _bundled_assets().values()


def get_assets_dir() -> Path:
    """Directory inside the installed package containing the files."""
    root = files("app_factory").joinpath("assets")
    return Path(str(root))


def platform_asset_url(name: str, *, prefix: str = "/static/platform") -> str:
    """Build a URL for a bundled asset under the given mount prefix.

    The host decides the prefix (e.g. "/static/platform" or "/_platform").
    """
    asset = bundled_asset(name)
    p = prefix.rstrip("/")
    return f"{p}/{asset.filename}"


# --- Optional Starlette mount (only when the fastapi extra is installed) ---


def get_platform_static_app() -> ASGIApp:
    """Return a Starlette app serving the package assets."""
    try:
        from starlette.staticfiles import StaticFiles
    except ImportError as exc:
        raise RuntimeError(
            "get_platform_static_app() requires the 'fastapi' extra"
        ) from exc
    return cast("ASGIApp", StaticFiles(directory=str(get_assets_dir()), check_dir=True))
