"""FastAPI composition contract for app-factory UI."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from jinja2 import DictLoader, Environment
from starlette.routing import Mount

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


@pytest.mark.parametrize("static_path", ["", "/", "relative"])
def test_static_path_must_be_an_absolute_non_root_path(static_path: str) -> None:
    with pytest.raises(ValueError):
        _ = install_app_factory_ui(FastAPI(), environments=[], static_path=static_path)
