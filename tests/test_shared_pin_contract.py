"""Cross-app pin contract: all factory consumers share the same core URLs."""

from __future__ import annotations

from app_factory.cdn import CDN_ASSET_MANIFEST, cdn_asset


def test_factory_pin_is_v0_2_0():
    css = cdn_asset("basecoat-css")
    js = cdn_asset("basecoat-js-all")
    assert css.version == "0.2.0"
    assert js.version == "0.2.0"
    assert "mikolaj92/basecoat-factory@v0.2.0" in css.url
    assert css.url.endswith("basecoat-factory.min.css")
    assert js.url.endswith("basecoat-js.min.js")


def test_core_order_stable():
    orders = [a.order for a in CDN_ASSET_MANIFEST]
    assert orders == sorted(orders)
    assert [a.name for a in CDN_ASSET_MANIFEST] == [
        "basecoat-css",
        "basecoat-js-all",
        "htmx",
        "alpine",
    ]
