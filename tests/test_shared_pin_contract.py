"""Cross-app contract for locally bundled core chrome."""

from __future__ import annotations

import json
from pathlib import Path

from app_factory.assets import bundled_asset, list_bundled_assets, platform_asset_url

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SRC = REPO_ROOT / "scripts" / "platform_assets_src"
REFRESH_SCRIPT = REPO_ROOT / "scripts" / "refresh_platform_assets.py"


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
        "landing-css",
        "landing-js",
    ]
    assert bundled_asset("alpine").version == "3.17.2"
    assert bundled_asset("htmx").version == "4.0.0"


def test_htmx_is_fetched_from_github_not_npm() -> None:
    package = json.loads((BUILD_SRC / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((BUILD_SRC / "package-lock.json").read_text(encoding="utf-8"))
    script = REFRESH_SCRIPT.read_text(encoding="utf-8")
    deps = {
        **package.get("dependencies", {}),
        **package.get("devDependencies", {}),
    }
    assert "htmx.org" not in deps
    assert "htmx.org" not in lock.get("packages", {})
    assert "node_modules/htmx.org" not in script
    assert "github.com/bigskysoftware/htmx" in script
    assert 'HTMX_VERSION = "4.0.0"' in script
