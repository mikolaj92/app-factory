"""Contract tests for shared CDN manifest."""

from __future__ import annotations

import pytest

from app_factory.cdn import (
    CDN_ASSET_MANIFEST,
    cdn_asset,
    extend_manifest,
    install_manifest,
)


def test_core_manifest_has_factory_and_htmx_alpine():
    names = [a.name for a in CDN_ASSET_MANIFEST]
    assert names == ["basecoat-css", "basecoat-js-all", "htmx", "alpine"]
    css = cdn_asset("basecoat-css")
    assert "basecoat-factory@v0.2.0" in css.url
    assert css.integrity.startswith("sha384-")


def test_extend_manifest_adds_chartjs():
    m = extend_manifest(["chartjs"])
    assert any(a.name == "chartjs" for a in m)
    assert len(m) == 5


def test_install_manifest_updates_lookup():
    original = CDN_ASSET_MANIFEST
    try:
        install_manifest(extend_manifest(["chartjs"]))
        assert cdn_asset("chartjs").version == "4.4.1"
    finally:
        install_manifest(original)


def test_unknown_asset_raises():
    with pytest.raises(KeyError):
        cdn_asset("not-a-real-asset-xyz")
