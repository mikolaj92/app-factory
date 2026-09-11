"""FastAPI composition contract for app-factory UI."""

from __future__ import annotations

import ast
import tomllib
from importlib.resources import files
from pathlib import Path

import pytest
from fastapi import FastAPI
from jinja2 import DictLoader, Environment
from starlette.routing import Mount
from starlette.testclient import TestClient

from app_factory import __version__
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


def test_platform_mount_serves_basecoat_js_and_omits_icon_fonts():
    app = FastAPI()
    install_app_factory_ui(app, environments=[])
    root = files("app_factory").joinpath("assets")
    client = TestClient(app)
    names = {path.name for path in Path(str(root)).iterdir()}
    assert "basecoat-js.min.js" in names
    assert "material-symbols.css" not in names
    assert "material-symbols-outlined.woff2" not in names
    js = client.get("/static/platform/basecoat-js.min.js")
    assert js.status_code == 200
    assert b"basecoat" in js.content.lower() or len(js.content) > 10_000
    assert client.get("/static/platform/material-symbols.css").status_code == 404


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


def test_platform_extra_matches_fastapi_and_import_errors_name_it() -> None:
    extras = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["optional-dependencies"]
    assert extras["fastapi"] == extras["platform"]
    sources = {
        Path("app_factory/platform.py"),
        Path("app_factory/fastapi.py"),
        Path("app_factory/csrf.py"),
        Path("app_factory/uploads.py"),
        Path("app_factory/responses.py"),
        Path("app_factory/conformance.py"),
    }
    for path in sources:
        text = (Path(__file__).parents[1] / path).read_text(encoding="utf-8")
        assert "requires app-factory[platform]" in text, path
        assert "requires app-factory[fastapi]" not in text, path


def test_optional_python_floors_track_current_latest() -> None:
    extras = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["optional-dependencies"]
    for extra in extras.values():
        assert "python-multipart>=0.0.32" in extra or all(
            not item.startswith("python-multipart") for item in extra
        )
        if any(item.startswith("pytest") for item in extra):
            assert "pytest>=9" in extra
        if any(item.startswith("ruff") for item in extra):
            assert "ruff>=0.16" in extra
        if any(item.startswith("playwright") for item in extra):
            assert "playwright>=1.62" in extra


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


def test_readme_bundled_assets_heading_matches_project_metadata() -> None:
    root = Path(__file__).parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert f"## Bundled core assets (`v{project['project']['version']}`)" in readme


def test_readme_export_table_covers_product_host_api() -> None:
    from app_factory import __all__ as public_names

    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    exports = readme.split("## What this package exports", 1)[1].split("## ", 1)[0]
    sketch = readme.split("## API sketch", 1)[1].split("## ", 1)[0]
    required = (
        "create_product_app",
        "install_product_host",
        "RunPort",
        "create_run_router",
        "create_run_view_router",
        "IntakeSpec",
        "create_intake_router",
        "check_thin_host",
    )
    for symbol in required:
        assert symbol in exports, symbol
        assert symbol in sketch, symbol
        assert symbol in public_names, symbol
    assert "product_shell.html" in exports
    assert "install_manifest" in public_names
    assert "install_manifest" in sketch


def test_bom_app_factory_pin_matches_project_version() -> None:
    root = Path(__file__).parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    bom = tomllib.loads((root / "bom" / "multi_user.toml").read_text(encoding="utf-8"))
    assert bom["pins"]["app-factory"] == f"v{project['project']['version']}"


def test_package_init_does_not_mask_internal_import_errors() -> None:
    root = Path(__file__).parents[1]
    tree = ast.parse((root / "app_factory" / "__init__.py").read_text(encoding="utf-8"))
    assigns_none = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name):
            if node.type.id != "ImportError":
                continue
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name) and target.id == "Run":
                            assigns_none = True
    assert not assigns_none


@pytest.mark.parametrize("static_path", ["", "/", "relative"])
def test_static_path_must_be_an_absolute_non_root_path(static_path: str) -> None:
    with pytest.raises(ValueError):
        _ = install_app_factory_ui(FastAPI(), environments=[], static_path=static_path)
