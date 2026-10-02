"""Published layout-only CSS is local, pinned, and isolated from UI themes."""

from importlib.resources import files
import re

from jinja2 import Environment

from app_factory.assets import bundled_asset, platform_asset_url
from app_factory.jinja import configure_jinja_env


def test_shared_views_use_layout_primitives_without_legacy_containers() -> None:
    templates = files("app_factory").joinpath("templates", "app_factory")
    for name in (
        "components/file_upload.html",
        "components/intake.html",
        "components/run_results.html",
        "platform_auth.html",
        "platform_sidebar.html",
    ):
        html = templates.joinpath(name).read_text()
        assert "l--stack" in html
        assert 'class="app-stack' not in html
    for name in (
        "platform_theme_locale.html",
        "platform_controls.html",
        "components/pagination.html",
    ):
        html = templates.joinpath(name).read_text()
        assert "l--cluster" in html
        assert 'class="app-cluster' not in html


def test_lism_layout_is_verified_and_loaded_by_both_heads() -> None:
    asset = bundled_asset("lism-layout")
    assert asset.version == "1.0.1"
    assert asset.kind == "style"
    css = files("app_factory").joinpath("assets", asset.filename).read_text()
    for primitive in (
        "stack",
        "cluster",
        "center",
        "autoColumns",
        "withSide",
        "switchColumns",
    ):
        assert f".l--{primitive}" in css
    assert "@layer layout" in css
    assert "--flow--base:" in css
    assert "--flow--s:" in css
    assert "--sz--xs:" in css
    for unwanted in ("--accent:", "--base:", "body{", "button{", "@layer reset"):
        assert re.search(r"(?<![\w-])" + re.escape(unwanted), css) is None
    environment = configure_jinja_env(Environment(autoescape=True))
    for name in ("head_assets.html", "head_assets_slim.html"):
        html = environment.get_template(f"app_factory/{name}").render()
        assert platform_asset_url(asset.name) in html
        assert html.index(asset.filename) < html.index("basecoat-factory.min.css")
        assert "tailwind.min.js" in html
    license_text = (
        files("app_factory")
        .joinpath("assets", "licenses", "lism-css.LICENSE")
        .read_text()
    )
    assert "Permission is hereby granted" in license_text
