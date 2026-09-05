"""FastAPI composition contract for app-factory UI."""

from __future__ import annotations

import base64
import hashlib
import tomllib
from importlib.resources import files
from pathlib import Path

import pytest
from fastapi import FastAPI
from jinja2 import DictLoader, Environment
from starlette.routing import Mount
from starlette.testclient import TestClient

from app_factory import __version__
from app_factory.assets import bundled_asset
from app_factory.fastapi import AppFactoryUiConflict, install_app_factory_ui


def _environment(content: str = "Ready") -> Environment:
    return Environment(
        loader=DictLoader(
            {
                "page.html": (
                    "{% extends 'app_factory/shell.html' %}"
                    + "{% block content %}"
                    + content
                    + "{% endblock %}"
                )
            }
        )
    )


def test_install_mounts_assets_and_configures_shell():
    app = FastAPI()
    environment = _environment()
    installed = install_app_factory_ui(app, environments=[environment])
    html = environment.get_template("page.html").render(app_name="Test")

    assert installed.asset_prefix == "/static/platform"
    assert "Ready" in html
    assert "/static/platform/basecoat-factory.min.css" in html
    assert 'id="app-main"' in html
    assert 'id="main-content"' in html

    mounts = [route for route in app.routes if isinstance(route, Mount)]
    assert [(route.path, route.name) for route in mounts] == [
        ("/static/platform", "app-factory-platform")
    ]


def test_material_symbols_assets_have_verified_digests_and_are_mounted():
    app = FastAPI()
    install_app_factory_ui(app, environments=[])
    root = files("app_factory").joinpath("assets")
    client = TestClient(app)

    for name, filename, kind in (
        ("material-symbols-css", "material-symbols.css", "style"),
        ("material-symbols-font", "material-symbols-outlined.woff2", "font"),
    ):
        asset = bundled_asset(name)
        raw = root.joinpath(filename).read_bytes()
        digest = "sha384-" + base64.b64encode(hashlib.sha384(raw).digest()).decode("ascii")
        assert asset.filename == filename
        assert asset.kind == kind
        assert asset.integrity == digest
        response = client.get(f"/static/platform/{filename}")
        assert response.status_code == 200
        assert response.content == raw
    mounts = [route for route in app.routes if isinstance(route, Mount)]
    assert [(route.path, route.name) for route in mounts] == [
        ("/static/platform", "app-factory-platform")
    ]


def test_install_is_idempotent_configures_new_environments_and_rejects_conflicts():
    app = FastAPI()
    first_environment = _environment()
    first = install_app_factory_ui(app, environments=[first_environment])
    second_environment = _environment("Second")

    assert install_app_factory_ui(app, environments=[second_environment]) == first
    assert "Second" in second_environment.get_template("page.html").render()
    with pytest.raises(AppFactoryUiConflict):
        _ = install_app_factory_ui(
            app,
            environments=[first_environment],
            static_path="/different",
        )


def test_shell_exposes_supported_product_frame_blocks():
    environment = _environment()
    _ = install_app_factory_ui(FastAPI(), environments=[environment])
    blocks = set(environment.get_template("app_factory/shell.html").blocks)
    assert {
        "title",
        "head_assets",
        "head_extra",
        "body_class",
        "body_attrs",
        "body",
        "navigation",
        "header",
        "loading_overlay",
        "loading_label",
        "content_class",
        "content",
        "page_scripts",
        "body_end",
    } <= blocks


def test_runtime_version_matches_project_metadata():
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert __version__ == project["project"]["version"]


def test_readme_current_tag_matches_project_metadata() -> None:
    root = Path(__file__).parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert f"**Tag:** `v{project['project']['version']}`" in readme


def test_bom_app_factory_pin_matches_project_version() -> None:
    root = Path(__file__).parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    bom = tomllib.loads((root / "bom" / "multi_user.toml").read_text(encoding="utf-8"))
    assert bom["pins"]["app-factory"] == f"v{project['project']['version']}"

@pytest.mark.parametrize("static_path", ["", "/", "relative"])
def test_static_path_must_be_an_absolute_non_root_path(static_path: str) -> None:
    with pytest.raises(ValueError):
        _ = install_app_factory_ui(FastAPI(), environments=[], static_path=static_path)
