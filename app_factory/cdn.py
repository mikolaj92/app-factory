"""Pinned optional CDN assets for product-specific integrations.

Core chrome is bundled locally; this registry contains only optional extras.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from typing import Literal, Protocol, cast
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

AssetKind = Literal["script", "style"]

_ALLOWED_HOST = "cdn.jsdelivr.net"


class CDNVerificationError(ValueError):
    """Raised when a CDN asset response fails an integrity or transport check."""


class CDNResponse(Protocol):
    status: int | None

    def read(self) -> bytes: ...

    def geturl(self) -> str: ...

    def getcode(self) -> int: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class CDNAsset:
    name: str
    version: str
    url: str
    integrity: str
    kind: AssetKind
    crossorigin: Literal["anonymous"] = "anonymous"
    defer: bool = False
    order: int = 0
    algorithm: Literal["sha384"] = "sha384"


# Optional well-known extras (not in core validate count)
OPTIONAL_ASSETS: dict[str, CDNAsset] = {
    "chartjs": CDNAsset(
        name="chartjs",
        version="4.4.1",
        url="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js",
        integrity="sha384-9nhczxUqK87bcKHh20fSQcTGD4qq5GhayNYSYWqwBkINBhOfQLg/P5HG5lF1urn4",
        kind="script",
        order=50,
    ),
    "leaflet-css": CDNAsset(
        name="leaflet-css",
        version="1.9.4",
        url="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css",
        integrity="sha384-sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H",
        kind="style",
        order=60,
    ),
    "leaflet-js": CDNAsset(
        name="leaflet-js",
        version="1.9.4",
        url="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js",
        integrity="sha384-cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH",
        kind="script",
        order=61,
    ),
    "sortablejs": CDNAsset(
        name="sortablejs",
        version="1.15.3",
        url="https://cdn.jsdelivr.net/npm/sortablejs@1.15.3/Sortable.min.js",
        integrity="sha384-/jkFGhPVLS9HIUzX09xB5W3coE5q1X5NXZA/PuOAdOaRxUPczlZmKzYEq9QcJnW0",
        kind="script",
        order=62,
    ),
}

CDN_ASSET_MANIFEST: tuple[CDNAsset, ...] = ()
_cdn_asset_manifest: tuple[CDNAsset, ...] = CDN_ASSET_MANIFEST
_approved_by_name: dict[str, CDNAsset] = {}


def _validate_manifest(manifest: tuple[CDNAsset, ...]) -> None:
    orders = [asset.order for asset in manifest]
    if orders != sorted(orders) or len(set(orders)) != len(orders):
        raise RuntimeError("CDN asset order values must be unique and ascending")
    for asset in manifest:
        parsed = urlsplit(asset.url)
        if parsed.scheme != "https" or parsed.hostname != _ALLOWED_HOST:
            raise RuntimeError(f"CDN asset has an unapproved URL: {asset.url}")
        if not asset.integrity.startswith("sha384-"):
            raise RuntimeError(
                f"CDN asset lacks a SHA-384 integrity value: {asset.name}"
            )
        if asset.crossorigin != "anonymous":
            raise RuntimeError(f"CDN asset must use anonymous CORS: {asset.name}")


_validate_manifest(_cdn_asset_manifest)


def extend_manifest(extras: Iterable[CDNAsset | str]) -> tuple[CDNAsset, ...]:
    """Return the installed optional manifest plus named or explicit extras."""
    assets: list[CDNAsset] = list(_cdn_asset_manifest)
    names = {a.name for a in assets}
    for item in extras:
        if isinstance(item, str):
            if item not in OPTIONAL_ASSETS:
                raise KeyError(f"unknown optional CDN asset: {item}")
            asset = OPTIONAL_ASSETS[item]
        else:
            asset = item
        if asset.name in names:
            continue
        assets.append(asset)
        names.add(asset.name)
    out = tuple(sorted(assets, key=lambda asset: asset.order))
    _validate_manifest(out)
    return out


def install_manifest(manifest: tuple[CDNAsset, ...]) -> None:
    """Replace the process-wide approved manifest (used by apps with extras)."""
    global _cdn_asset_manifest, _approved_by_name
    _validate_manifest(manifest)
    _cdn_asset_manifest = manifest
    _approved_by_name = {a.name: a for a in manifest}
    globals()["CDN_ASSET_MANIFEST"] = manifest


def cdn_asset(name: str) -> CDNAsset:
    try:
        return _approved_by_name[name]
    except KeyError as exc:
        # Fall back to optional catalog without installing
        if name in OPTIONAL_ASSETS:
            return OPTIONAL_ASSETS[name]
        raise KeyError(f"unknown CDN asset: {name}") from exc


Fetcher = Callable[[str], CDNResponse]


def _open_url(url: str, *, timeout: float) -> CDNResponse:
    request = Request(url, headers={"Accept": "*/*"})
    return cast(CDNResponse, urlopen(request, timeout=timeout))


def verify_cdn_asset(
    asset: CDNAsset,
    *,
    fetcher: Fetcher | None = None,
    timeout: float = 10.0,
) -> None:
    approved = _approved_by_name.get(asset.name) or OPTIONAL_ASSETS.get(asset.name)
    if (
        approved is None
        or asset.version != approved.version
        or asset.url != approved.url
        or asset.kind != approved.kind
    ) and (approved is None or asset.url != approved.url):
        raise CDNVerificationError(f"unexpected requested CDN URL: {asset.url}")

    response = (
        fetcher(asset.url)
        if fetcher is not None
        else _open_url(asset.url, timeout=timeout)
    )
    try:
        status = getattr(response, "status", None)
        if status is None:
            status = response.getcode()
        if not 200 <= int(status) < 300:
            raise CDNVerificationError(
                f"CDN response returned HTTP {status}: {asset.url}"
            )

        final_url = response.geturl()
        final_parts = urlsplit(final_url)
        if final_parts.hostname != _ALLOWED_HOST:
            raise CDNVerificationError(
                f"CDN redirect reached unexpected host: {final_url}"
            )
        if final_url != asset.url:
            raise CDNVerificationError(
                f"CDN redirect reached unexpected URL: {final_url}"
            )
        body = response.read()
        digest = "sha384-" + base64.b64encode(hashlib.sha384(body).digest()).decode(
            "ascii"
        )
        if not hmac.compare_digest(digest, asset.integrity):
            raise CDNVerificationError(f"CDN integrity digest mismatch: {asset.name}")
    finally:
        response.close()


def verify_cdn_manifest(
    *,
    fetcher: Fetcher | None = None,
    timeout: float = 10.0,
) -> None:
    for asset in _cdn_asset_manifest:
        verify_cdn_asset(asset, fetcher=fetcher, timeout=timeout)


def asset_with_local_url(asset: CDNAsset, url: str) -> CDNAsset:
    """Copy an asset pointing at a same-origin/vendor URL (no SRI required)."""
    return replace(asset, url=url, integrity="", crossorigin="anonymous")
