"""Cross-app contract for locally bundled core chrome."""

from __future__ import annotations

from app_factory.assets import bundled_asset, list_bundled_assets, platform_asset_url


def test_factory_assets_share_the_generated_versions():
    css = bundled_asset("basecoat-css")
    js = bundled_asset("basecoat-js-all")
    assert css.version == js.version == "1.0.2"
    assert platform_asset_url(css.name).endswith("/basecoat-factory.min.css")
    assert platform_asset_url(js.name).endswith("/basecoat-js.min.js")


def test_core_names_are_stable():
    assert [asset.name for asset in list_bundled_assets()] == [
        "alpine",
        "basecoat-css",
        "basecoat-js-all",
        "htmx",
    ]
