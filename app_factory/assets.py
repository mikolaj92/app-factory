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
from typing import Literal, cast

AssetKind = Literal["script", "style"]

_CORE_NAMES = {"basecoat-css", "basecoat-js-all", "htmx", "alpine"}


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
    raw = json.loads(root.joinpath("MANIFEST.json").read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != _CORE_NAMES:
        raise RuntimeError("invalid bundled asset manifest names")

    assets: dict[str, BundledAsset] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not isinstance(value, dict):
            raise RuntimeError("invalid bundled asset manifest entry")
        filename = value.get("filename")
        version = value.get("version")
        integrity = value.get("integrity")
        kind = value.get("kind")
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or not isinstance(version, str)
            or not version
            or not isinstance(integrity, str)
            or not integrity.startswith("sha384-")
            or kind not in ("script", "style")
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
            kind=cast(AssetKind, kind),
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

def get_platform_static_app() -> object:
    """Return a Starlette app serving the package assets."""
    try:
        from starlette.staticfiles import StaticFiles  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "get_platform_static_app() requires the 'fastapi' extra"
        ) from exc
    return StaticFiles(directory=str(get_assets_dir()), check_dir=True)
