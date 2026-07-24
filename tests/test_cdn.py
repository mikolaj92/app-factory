"""Contracts for bundled core assets and optional CDN extras."""

from __future__ import annotations

import pytest
import base64
import hashlib
from importlib.resources import files

from jinja2 import Environment

from app_factory.assets import bundled_asset, list_bundled_assets
from app_factory.jinja import configure_jinja_env

from app_factory.cdn import (
    CDN_ASSET_MANIFEST,
    cdn_asset,
    extend_manifest,
    install_manifest,
)


def test_core_assets_are_local_and_manifest_verified():
    assert CDN_ASSET_MANIFEST == ()
    assets = list(list_bundled_assets())
    assert [asset.name for asset in assets] == [
        "alpine",
        "basecoat-css",
        "basecoat-js-all",
        "htmx",
    ]
    root = files("app_factory").joinpath("assets")
    for asset in assets:
        digest = "sha384-" + base64.b64encode(
            hashlib.sha384(root.joinpath(asset.filename).read_bytes()).digest()
        ).decode("ascii")
        assert asset.integrity == digest
    assert root.joinpath(bundled_asset("basecoat-js-all").filename).stat().st_size > 10_000


def test_extend_manifest_adds_chartjs():
    m = extend_manifest(["chartjs"])
    assert [asset.name for asset in m] == ["chartjs"]
    assert len(m) == 1


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

def test_head_partial_uses_only_same_origin_core_assets():
    env = configure_jinja_env(Environment(autoescape=True))
    rendered = env.get_template("app_factory/head_assets.html").render()
    assert "https://" not in rendered
    assert "/static/platform/basecoat-factory.min.css" in rendered
    assert "/static/platform/basecoat-js.min.js" in rendered
    assert "/static/platform/htmx.min.js" in rendered
    assert "/static/platform/alpine.min.js" in rendered

# --- Local bundled assets contract (package data) ---
# These tests run against the final assets inside the installed package
# (app_factory/assets/...), not the build sources.
# They verify that the deterministic maintainer script produced something
# that actually ships and contains the required selectors.

def test_local_bundled_assets_are_present_via_importlib_resources():
    """The wheel must contain all core files and required CSS selectors."""
    assets = files("app_factory").joinpath("assets")
    assert assets.is_dir(), "app_factory/assets not found in package data"

    css = assets.joinpath("basecoat-factory.min.css")
    assert css.is_file(), "basecoat-factory.min.css missing from package assets"

    js_files = [
        "basecoat-js.min.js",
        "htmx.min.js",
        "alpine.min.js",
    ]
    for name in js_files:
        assert assets.joinpath(name).is_file(), f"{name} missing from package assets"

    # Read CSS content and check for concrete required selectors (new baseline contract)
    content = css.read_text(encoding="utf-8")
    required = [
        ".btn",           # basecoat
        ".card",          # basecoat
        ".mt-4",
        ".flex",
        ".grid-cols-3",
        ".hidden",
        ".items-center",
        ".justify-between",
        ".app-table-wrap",
        ".app-dropzone",
        ".app-progress",
    ]
    missing = [sel for sel in required if sel not in content]
    assert not missing, f"bundled baseline CSS missing selectors: {missing}"
