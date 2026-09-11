"""Contracts for bundled core assets and optional CDN extras."""

from __future__ import annotations

import base64
import hashlib
from importlib.resources import files
from pathlib import Path

import pytest
from jinja2 import Environment

from app_factory.assets import bundled_asset, list_bundled_assets
from app_factory.cdn import (
    CDN_ASSET_MANIFEST,
    cdn_asset,
    extend_manifest,
    install_manifest,
)
from app_factory.jinja import configure_jinja_env


def test_core_assets_are_local_and_manifest_verified():
    assert CDN_ASSET_MANIFEST == ()
    assets = list(list_bundled_assets())
    assert [asset.name for asset in assets] == [
        "alpine",
        "basecoat-css",
        "basecoat-js-all",
        "htmx",
        "landing-css",
        "landing-js",
        "tailwind-browser",
    ]
    assert bundled_asset("alpine").version == "3.17.2"
    assert bundled_asset("basecoat-css").version == "1.0.2"
    assert bundled_asset("basecoat-js-all").version == "1.0.2"
    assert bundled_asset("htmx").version == "4.0.0"
    assert bundled_asset("tailwind-browser").version == "4.3.3"
    root = files("app_factory").joinpath("assets")
    for asset in assets:
        digest = "sha384-" + base64.b64encode(
            hashlib.sha384(root.joinpath(asset.filename).read_bytes()).digest()
        ).decode("ascii")
        assert asset.integrity == digest
    assert (
        Path(str(root.joinpath(bundled_asset("basecoat-js-all").filename)))
        .stat()
        .st_size
        > 10_000
    )


def test_extend_manifest_adds_chartjs():
    m = extend_manifest(["chartjs"])
    assert [asset.name for asset in m] == ["chartjs"]
    assert len(m) == 1
    assert cdn_asset("chartjs").version == "4.5.1"
    assert cdn_asset("sortablejs").version == "1.15.7"
    assert "4.4.1" not in cdn_asset("chartjs").url
    assert "1.15.3" not in cdn_asset("sortablejs").url


def test_install_manifest_updates_lookup():
    original = CDN_ASSET_MANIFEST
    try:
        install_manifest(extend_manifest(["chartjs"]))
        assert cdn_asset("chartjs").version == "4.5.1"
    finally:
        install_manifest(original)


def test_unknown_asset_raises():
    with pytest.raises(KeyError):
        _ = cdn_asset("not-a-real-asset-xyz")


def test_head_partial_uses_only_same_origin_core_assets():
    env = configure_jinja_env(Environment(autoescape=True))
    rendered = env.get_template("app_factory/head_assets.html").render()
    assert "https://" not in rendered
    assert "/static/platform/basecoat-factory.min.css" in rendered
    assert "/static/platform/basecoat-js.min.js" in rendered
    assert "/static/platform/htmx.min.js" in rendered
    assert "/static/platform/alpine.min.js" in rendered
    assert "/static/platform/tailwind.min.js" in rendered
    assert 'type="text/tailwindcss"' in rendered
    assert "@custom-variant dark" in rendered
    assert "--color-background: var(--background)" in rendered
    assert "htmx:config:request" in rendered
    assert "htmx:after:swap" in rendered
    assert "htmx:response:error" in rendered
    assert "htmx:configRequest" not in rendered
    assert "material-symbols" not in rendered
    assert "unpkg.com" not in rendered
    assert "cdn.jsdelivr.net" not in rendered


def test_slim_head_partial_omits_htmx_and_alpine():
    env = configure_jinja_env(Environment(autoescape=True))
    rendered = env.get_template("app_factory/head_assets_slim.html").render()
    assert "https://" not in rendered
    assert "/static/platform/basecoat-factory.min.css" in rendered
    assert "/static/platform/basecoat-js.min.js" in rendered
    assert "/static/platform/tailwind.min.js" in rendered
    assert 'type="text/tailwindcss"' in rendered
    assert "@custom-variant dark" in rendered
    assert "--color-background: var(--background)" in rendered
    assert "@layer theme {" in rendered
    assert '@import "tailwindcss/theme";' in rendered
    assert "@layer utilities {" in rendered
    assert '@import "tailwindcss/utilities";' in rendered
    assert material_import_is_wrapped(rendered)
    assert "material-symbols" not in rendered
    assert "/static/platform/htmx.min.js" not in rendered
    assert "/static/platform/alpine.min.js" not in rendered


def material_import_is_wrapped(rendered: str) -> bool:
    theme = rendered.split("@layer theme {", 1)
    utilities = rendered.split("@layer utilities {", 1)
    return (
        len(theme) == 2
        and "tailwindcss/theme" in theme[1].split("}", 1)[0]
        and len(utilities) == 2
        and "tailwindcss/utilities" in utilities[1].split("}", 1)[0]
    )


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
        "tailwind.min.js",
    ]
    for name in js_files:
        assert assets.joinpath(name).is_file(), f"{name} missing from package assets"

    # Read CSS content and check for concrete required selectors (new baseline contract)
    content = css.read_text(encoding="utf-8")
    required = [
        # Basecoat UI (hosts must not install basecoat/tailwind themselves)
        ".btn",
        ".card",
        ".input",
        ".field",
        ".table",
        ".table-container",
        ".sidebar",
        ".dialog",
        # Host-facing layout primitives (keep-list; rnkstr/emitype depend on these)
        ".app-page",
        ".app-stack",
        ".app-stack--tight",
        ".app-stack--sm",
        ".app-header",
        ".app-cluster",
        ".app-card-grid",
        ".app-form__field",
        ".app-shell",
        ".app-main",
        # Product surface helpers
        ".app-table-wrap",
        ".app-dropzone",
        ".app-progress",
    ]
    missing = [sel for sel in required if sel not in content]
    assert not missing, f"bundled baseline CSS missing selectors: {missing}"

    # Dead dual-class aliases must stay gone (not part of the host contract).
    forbidden_aliases = (
        "factory-shell",
        "factory-main",
        "factory-stack",
        "factory-cluster",
        "factory-page-header",
        "factory-content",
    )
    present = [name for name in forbidden_aliases if name in content]
    assert not present, (
        f"bundled CSS still contains removed factory-* aliases: {present}"
    )


def test_bundled_css_hosts_need_no_tailwind_or_basecoat_install():
    """Hard guarantee: product hosts consume this package only.

    The shipped CSS must include Basecoat components and host-facing .app-*
    layout primitives. Arbitrary Tailwind utilities come from the bundled
    browser engine, not a factory safelist. Integrity/size checks stop an
    empty or swapped bundle from greening tests.
    """
    root = files("app_factory").joinpath("assets")
    css_name = "basecoat-factory.min.css"
    css_path = root.joinpath(css_name)
    raw = css_path.read_bytes()
    content = raw.decode("utf-8")

    # Manifest integrity must match the bytes hosts actually download.
    css_asset = bundled_asset("basecoat-css")
    digest = "sha384-" + base64.b64encode(hashlib.sha384(raw).digest()).decode("ascii")
    assert css_asset.filename == css_name
    assert css_asset.integrity == digest
    assert css_asset.version == "1.0.2"

    # Size floors: a stub/minified-away bundle must fail loudly.
    assert len(raw) > 100_000, f"CSS too small to be full Basecoat: {len(raw)}"
    for name, minimum in (
        ("basecoat-js.min.js", 10_000),
        ("htmx.min.js", 10_000),
        ("alpine.min.js", 10_000),
        ("tailwind.min.js", 100_000),
    ):
        size = root.joinpath(name).stat().st_size
        assert size > minimum, f"{name} too small ({size} <= {minimum})"

    basecoat = [
        ".btn",
        ".card",
        ".input",
        ".textarea",
        ".select",
        ".label",
        ".field",
        ".fieldset",
        ".table",
        ".table-container",
        ".sidebar",
        ".dialog",
        ".dropdown-menu",
        ".popover",
        ".tabs",
        ".accordion",
        ".toast",
        ".toaster",
        ".badge",
        ".alert",
        ".progress",
        ".spinner",
        ".avatar",
    ]
    layout = [
        ".app-page",
        ".app-stack",
        ".app-stack--tight",
        ".app-stack--sm",
        ".app-stack--compact",
        ".app-header",
        ".app-cluster",
        ".app-card-grid",
        ".app-form__field",
        ".app-shell",
        ".app-main",
        ".app-table-wrap",
        ".app-dropzone",
        ".app-progress",
    ]
    missing = [sel for sel in (*basecoat, *layout) if sel not in content]
    assert not missing, f"bundle missing host-facing selectors: {missing}"

    forbidden = (
        "factory-shell",
        "factory-main",
        "factory-stack",
        "factory-cluster",
        "factory-page-header",
        "factory-content",
    )
    present = [name for name in forbidden if name in content]
    assert not present, f"removed factory-* aliases still in bundle: {present}"


def test_static_css_does_not_ship_a_tailwind_safelist():
    """Hosts may use any Tailwind class; the factory CSS is not the utility set."""
    css = files("app_factory").joinpath("assets", "basecoat-factory.min.css")
    content = css.read_text(encoding="utf-8")
    leaked = [
        sel
        for sel in (".flex{", ".gap-2{", ".mt-4{", ".grid-cols-3{")
        if sel in content
    ]
    assert not leaked, f"static CSS still contains a Tailwind safelist: {leaked}"
