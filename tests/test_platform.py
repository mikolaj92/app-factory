"""Platform composition: context, shell foot, install path."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from jinja2 import DictLoader, Environment, PackageLoader, ChoiceLoader
from starlette.testclient import TestClient

from app_factory.platform import (
    FORBIDDEN_BASECOAT_CLASS_MARKERS,
    MenuItem,
    PlatformConfig,
    PlatformLocale,
    PlatformPaths,
    PlatformUser,
    apply_platform_context,
    build_platform_context,
    install_platform,
)


def _env_with_factory() -> Environment:
    return Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        "page.html": (
                            "{% extends 'app_factory/product_shell.html' %}"
                            "{% block content %}BODY{% endblock %}"
                        )
                    }
                ),
                PackageLoader("app_factory", "templates"),
            ]
        ),
        autoescape=True,
    )


def test_build_platform_context_guest_vs_user() -> None:
    config = PlatformConfig(
        app_name="Demo",
        menu=(MenuItem("Home", "/"), MenuItem("Queue", "/queue")),
        paths=PlatformPaths(
            login="/login", logout="/logout", account="/account"
        ),
        enable_admin_users=True,
    )
    guest = build_platform_context(config, current_path="/queue")
    assert guest["platform_user"] is None
    assert guest["login_url"] == "/login"
    assert guest["platform_menu"][1].active is True

    user = build_platform_context(
        config,
        user=PlatformUser(display_name="Ops", is_admin=True, user_id="u1"),
        current_path="/",
    )
    assert user["platform_user"].display_name == "Ops"
    assert user["platform_user"].is_admin is True


def test_product_shell_renders_platform_foot_for_guest_and_user() -> None:
    app = FastAPI()
    environment = _env_with_factory()
    config = PlatformConfig(
        app_name="Demo",
        menu=(MenuItem("Home", "/"),),
        paths=PlatformPaths(),
    )
    install_platform(app, environments=[environment], config=config)

    guest_html = environment.get_template("page.html").render()
    assert "data-platform-foot" in guest_html
    assert "data-platform-controls" in guest_html
    assert "Login" in guest_html
    assert 'href="/login"' in guest_html
    assert "Theme" in guest_html
    assert "btn-primary" not in guest_html
    assert 'data-variant="primary"' in guest_html
    assert "BODY" in guest_html
    assert "/static/platform/basecoat-factory.min.css" in guest_html
    # No language row when host does not configure locales.
    assert "data-platform-locales" not in guest_html

    apply_platform_context(
        environment,
        config,
        user=PlatformUser(display_name="Alice", is_admin=False),
    )
    user_html = environment.get_template("page.html").render()
    assert "Alice" in user_html
    assert "Logout" in user_html
    assert 'action="/logout"' in user_html
    assert "Login" not in user_html or "Logout" in user_html


def test_platform_foot_renders_optional_locales() -> None:
    app = FastAPI()
    environment = _env_with_factory()
    config = PlatformConfig(app_name="Demo", paths=PlatformPaths())
    install_platform(app, environments=[environment], config=config)
    apply_platform_context(
        environment,
        config,
        locales=(
            PlatformLocale(code="pl", label="PL", href="/?lang=pl"),
            PlatformLocale(code="en", label="EN", href="/?lang=en"),
        ),
        locale="pl",
    )
    html = environment.get_template("page.html").render()
    assert "data-platform-locales" in html
    assert 'href="/?lang=pl"' in html
    assert 'href="/?lang=en"' in html
    assert 'data-locale="pl"' in html
    assert 'aria-current="page"' in html

    # Client-side locale buttons (no href) for SPA/i18n hosts.
    apply_platform_context(
        environment,
        config,
        locales=(
            PlatformLocale(code="pl", label="PL"),
            PlatformLocale(code="en", label="EN"),
        ),
        locale="en",
    )
    client_html = environment.get_template("page.html").render()
    assert "data-platform-locale-select" in client_html
    assert 'data-locale="en"' in client_html



def test_install_platform_mounts_chrome_and_registers_state() -> None:
    app = FastAPI()
    environment = _env_with_factory()
    result = install_platform(
        app,
        environments=[environment],
        config=PlatformConfig(app_name="X"),
    )
    assert result.ui.static_path == "/static/platform"
    assert result.passkey_ui is None
    assert getattr(app.state, "app_factory_platform") is result

    client = TestClient(app)
    # Bundled CSS is mounted under platform static
    css = client.get("/static/platform/basecoat-factory.min.css")
    assert css.status_code == 200
    assert len(css.content) > 100


def test_platform_templates_forbid_pre_basecoat_class_names() -> None:
    root = Path(__file__).resolve().parents[1] / "app_factory" / "templates"
    offenders: list[str] = []
    for path in root.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        # strip jinja comments
        body = "\n".join(
            line for line in text.splitlines() if not line.strip().startswith("{#")
        )
        for marker in FORBIDDEN_BASECOAT_CLASS_MARKERS:
            if marker in body:
                offenders.append(f"{path.name}:{marker}")
    assert offenders == []


def test_passkey_partial_install_requires_both_args() -> None:
    app = FastAPI()
    with pytest.raises(ValueError, match="both"):
        install_platform(
            app,
            environments=[],
            passkey_service=object(),
            passkey_hooks=None,
        )
