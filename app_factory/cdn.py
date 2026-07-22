"""Pinned third-party CDN assets for host apps.

Core pin: basecoat-factory (Basecoat + utilities + app-shell) + htmx + alpine.
Optional extras (chartjs, leaflet, …) via :func:`extend_manifest` or by name
lookup after registration.

Importing this module never performs network I/O.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass, replace
from typing import Callable, Iterable, Literal, Protocol
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

AssetKind = Literal["script", "style"]

_ALLOWED_HOST = "cdn.jsdelivr.net"


class CDNVerificationError(ValueError):
    """Raised when a CDN asset response fails an integrity or transport check."""


class CDNResponse(Protocol):
    status: int

    def read(self) -> bytes: ...

    def geturl(self) -> str: ...

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


# basecoat-factory@v0.2.0 — https://github.com/mikolaj92/basecoat-factory
_CORE: tuple[CDNAsset, ...] = (
    CDNAsset(
        name="basecoat-css",
        version="0.2.0",
        url="https://cdn.jsdelivr.net/gh/mikolaj92/basecoat-factory@v0.2.0/dist/basecoat-factory.min.css",
        integrity="sha384-yTWLxHpctVA4TCmRqP+h0CCXfSSzQW89Hbcck6TPoobuRVMH67ZP6KjDoM6Dfu1D",
        kind="style",
        order=10,
    ),
    CDNAsset(
        name="basecoat-js-all",
        version="0.2.0",
        url="https://cdn.jsdelivr.net/gh/mikolaj92/basecoat-factory@v0.2.0/dist/basecoat-js.min.js",
        integrity="sha384-Nh+vuYF6cR32jKYrKMif2BIAyNAYtifVdaSvCBc2IheqqAAuNII7/hWSWy6dIdmr",
        kind="script",
        defer=True,
        order=20,
    ),
    CDNAsset(
        name="htmx",
        version="2.0.10",
        url="https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js",
        integrity="sha384-H5SrcfygHmAuTDZphMHqBJLc3FhssKjG7w/CeCpFReSfwBWDTKpkzPP8c+cLsK+V",
        kind="script",
        order=30,
    ),
    CDNAsset(
        name="alpine",
        version="3.15.12",
        url="https://cdn.jsdelivr.net/npm/alpinejs@3.15.12/dist/cdn.min.js",
        integrity="sha384-pb6hrQvo4s23cEUFtj0CZkzGE3jyK3pj26RIupXXxhSrrcUA/Cn0lZgcCrGH0t6L",
        kind="script",
        defer=True,
        order=40,
    ),
)

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

CDN_ASSET_MANIFEST: tuple[CDNAsset, ...] = _CORE
_APPROVED_BY_NAME: dict[str, CDNAsset] = {a.name: a for a in CDN_ASSET_MANIFEST}


def _validate_core(manifest: tuple[CDNAsset, ...]) -> None:
    if not manifest:
        raise RuntimeError("CDN asset manifest is empty")
    orders = [asset.order for asset in manifest]
    if orders != sorted(orders) or len(set(orders)) != len(orders):
        raise RuntimeError("CDN asset order values must be unique and ascending")
    for asset in manifest:
        parsed = urlsplit(asset.url)
        if parsed.scheme != "https" or parsed.hostname != _ALLOWED_HOST:
            raise RuntimeError(f"CDN asset has an unapproved URL: {asset.url}")
        if not asset.integrity.startswith("sha384-"):
            raise RuntimeError(f"CDN asset lacks a SHA-384 integrity value: {asset.name}")
        if asset.crossorigin != "anonymous":
            raise RuntimeError(f"CDN asset must use anonymous CORS: {asset.name}")


_validate_core(CDN_ASSET_MANIFEST)


def extend_manifest(extras: Iterable[CDNAsset | str]) -> tuple[CDNAsset, ...]:
    """Return core manifest plus named optional extras or CDNAsset instances.

    Does not mutate the module-level default; callers that need a custom
    registry should pass the result into :func:`install_manifest`.
    """
    assets: list[CDNAsset] = list(CDN_ASSET_MANIFEST)
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
    out = tuple(sorted(assets, key=lambda a: a.order))
    _validate_core(out)
    return out


def install_manifest(manifest: tuple[CDNAsset, ...]) -> None:
    """Replace the process-wide approved manifest (used by apps with extras)."""
    global CDN_ASSET_MANIFEST, _APPROVED_BY_NAME
    _validate_core(manifest)
    CDN_ASSET_MANIFEST = manifest
    _APPROVED_BY_NAME = {a.name: a for a in manifest}


def cdn_asset(name: str) -> CDNAsset:
    try:
        return _APPROVED_BY_NAME[name]
    except KeyError as exc:
        # Fall back to optional catalog without installing
        if name in OPTIONAL_ASSETS:
            return OPTIONAL_ASSETS[name]
        raise KeyError(f"unknown CDN asset: {name}") from exc


Fetcher = Callable[[str], CDNResponse]


def _open_url(url: str, *, timeout: float) -> CDNResponse:
    request = Request(url, headers={"Accept": "*/*"})
    return urlopen(request, timeout=timeout)  # noqa: S310 - URL is manifest-pinned


def verify_cdn_asset(
    asset: CDNAsset,
    *,
    fetcher: Fetcher | None = None,
    timeout: float = 10.0,
) -> None:
    approved = _APPROVED_BY_NAME.get(asset.name) or OPTIONAL_ASSETS.get(asset.name)
    if approved is None or (
        asset.version != approved.version
        or asset.url != approved.url
        or asset.kind != approved.kind
    ):
        # Allow verifying the exact object if it is the approved one by URL
        if approved is None or asset.url != approved.url:
            raise CDNVerificationError(f"unexpected requested CDN URL: {asset.url}")

    response = fetcher(asset.url) if fetcher is not None else _open_url(asset.url, timeout=timeout)
    try:
        status = getattr(response, "status", None)
        if status is None:
            status = response.getcode()  # type: ignore[attr-defined]
        if not 200 <= int(status) < 300:
            raise CDNVerificationError(f"CDN response returned HTTP {status}: {asset.url}")

        final_url = response.geturl()
        final_parts = urlsplit(final_url)
        if final_parts.hostname != _ALLOWED_HOST:
            raise CDNVerificationError(f"CDN redirect reached unexpected host: {final_url}")
        if final_url != asset.url:
            raise CDNVerificationError(f"CDN redirect reached unexpected URL: {final_url}")
        body = response.read()
        digest = "sha384-" + base64.b64encode(hashlib.sha384(body).digest()).decode("ascii")
        if not hmac.compare_digest(digest, asset.integrity):
            raise CDNVerificationError(f"CDN integrity digest mismatch: {asset.name}")
    finally:
        response.close()


def verify_cdn_manifest(
    *,
    fetcher: Fetcher | None = None,
    timeout: float = 10.0,
) -> None:
    for asset in CDN_ASSET_MANIFEST:
        verify_cdn_asset(asset, fetcher=fetcher, timeout=timeout)


def asset_with_local_url(asset: CDNAsset, url: str) -> CDNAsset:
    """Copy an asset pointing at a same-origin/vendor URL (no SRI required)."""
    return replace(asset, url=url, integrity="", crossorigin="anonymous")
