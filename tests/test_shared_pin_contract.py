"""Cross-app contract for locally bundled core chrome."""

from __future__ import annotations

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
        "tailwind-browser",
    ]
    assert bundled_asset("alpine").version == "3.17.2"
    assert bundled_asset("htmx").version == "4.0.0"
    assert bundled_asset("tailwind-browser").version == "4.3.3"


def test_readme_lists_every_manifest_pin() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for asset in list_bundled_assets():
        assert f"| `{asset.name}` |" in readme
    assert "four bundled core files" not in readme


def test_maintainer_build_has_no_npm_lock() -> None:
    assert not (BUILD_SRC / "package.json").exists()
    assert not (BUILD_SRC / "package-lock.json").exists()
    script = REFRESH_SCRIPT.read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "npm ci" not in script
    assert "npm run" not in script
    assert "node_modules" not in script
    assert "npm lockfile" not in readme
    assert "npm ci" not in readme
    assert "node_modules" not in gitignore


def test_htmx_is_fetched_from_github_not_npm() -> None:
    script = REFRESH_SCRIPT.read_text(encoding="utf-8")
    assert "node_modules/htmx.org" not in script
    assert "github.com/bigskysoftware/htmx" in script
    assert 'HTMX_VERSION = "4.0.0"' in script


def test_alpine_is_fetched_without_npm_dependency() -> None:
    script = REFRESH_SCRIPT.read_text(encoding="utf-8")
    assert "node_modules/alpinejs" not in script
    assert 'ALPINE_VERSION = "3.17.2"' in script
    assert "registry.npmjs.org/alpinejs" in script


def test_basecoat_is_fetched_without_npm_dependency() -> None:
    script = REFRESH_SCRIPT.read_text(encoding="utf-8")
    assert "node_modules/basecoat-css" not in script
    assert 'BASECOAT_VERSION = "1.0.2"' in script
    assert "registry.npmjs.org/basecoat-css" in script


def test_tailwind_browser_is_fetched_without_npm_dependency() -> None:
    script = REFRESH_SCRIPT.read_text(encoding="utf-8")
    assert "node_modules/@tailwindcss/browser" not in script
    assert "node_modules/tailwindcss" not in script
    assert 'TAILWIND_BROWSER_VERSION = "4.3.3"' in script
    assert "registry.npmjs.org/@tailwindcss/browser" in script
    tw = bundled_asset("tailwind-browser")
    assert tw.filename == "tailwind.min.js"
    assert tw.kind == "script"
    assert platform_asset_url(tw.name).endswith("/tailwind.min.js")


def test_hosts_must_not_vendor_the_tailwind_engine() -> None:
    from app_factory.conformance import FORBIDDEN_ASSETS

    assert "tailwind.min.js" in FORBIDDEN_ASSETS
