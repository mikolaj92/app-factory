"""Platform composition: context, shell foot, install path."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from jinja2 import DictLoader, Environment, PackageLoader, ChoiceLoader
from starlette.testclient import TestClient

from app_factory.platform import (
    FORBIDDEN_BASECOAT_CLASS_MARKERS,
    MenuGroup,
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
    assert "data-platform-auth" in guest_html
    assert "Login" in guest_html
    assert 'href="/login"' in guest_html
    # Theme lives in header partial, not the sidebar foot (script still mentions the attr).
    foot_start = guest_html.find("data-platform-foot")
    assert foot_start != -1
    foot_chunk = guest_html[foot_start : foot_start + 1200]
    assert "data-theme-toggle" not in foot_chunk
    assert "data-platform-auth" in foot_chunk
    assert "btn-primary" not in guest_html
    assert 'data-variant="primary"' in guest_html
    assert "BODY" in guest_html
    assert 'id="app-main"' in guest_html
    assert 'id="main-content"' in guest_html
    assert 'id="sidebar"' in guest_html
    assert "data-sidebar-toggle" in guest_html
    assert "data-platform-theme-locale" in guest_html
    assert "app-main-header" in guest_html
    assert "/static/platform/basecoat-factory.min.css" in guest_html
    assert "data-platform-locales" not in guest_html

    apply_platform_context(
        environment,
        config,
        user=PlatformUser(display_name="Alice", is_admin=False),
    )
    user_html = environment.get_template("page.html").render()
    assert "Alice" in user_html
    assert 'data-platform-account-link' in user_html
    # Logout is not in chrome — only on the account page partial.
    foot = user_html[user_html.find("data-platform-foot") :][:1500]
    assert "Log out" not in foot
    assert "Logout" not in foot
    assert "Login" not in foot


def test_platform_theme_locale_partial() -> None:
    environment = _env_with_factory()
    environment.loader.loaders[0].mapping["header.html"] = (
        "{% include 'app_factory/platform_theme_locale.html' %}"
    )
    # ChoiceLoader uses DictLoader first — rebuild env with partial
    from jinja2 import ChoiceLoader, DictLoader, Environment, PackageLoader

    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        "header.html": (
                            "{% include 'app_factory/platform_theme_locale.html' %}"
                        )
                    }
                ),
                PackageLoader("app_factory", "templates"),
            ]
        ),
        autoescape=True,
    )
    apply_platform_context(
        env,
        PlatformConfig(paths=PlatformPaths()),
        locales=(
            PlatformLocale(code="pl", label="PL", href="/?lang=pl"),
            PlatformLocale(code="en", label="EN", href="/?lang=en"),
        ),
        locale="pl",
    )
    html = env.get_template("header.html").render()
    assert "data-platform-theme-locale" in html
    assert "data-theme-toggle" in html
    assert "theme-toggle-icon--light" in html
    assert "onclick=" not in html  # shell_boot owns the click (no double toggle)
    assert "data-platform-locales" in html
    assert 'href="/?lang=pl"' in html
    assert "data-platform-locale-select" not in html

    apply_platform_context(
        env,
        PlatformConfig(paths=PlatformPaths()),
        locales=(
            PlatformLocale(code="pl", label="PL"),
            PlatformLocale(code="en", label="EN"),
        ),
        locale="en",
    )
    client_html = env.get_template("header.html").render()
    assert "data-platform-locale-select" in client_html


def test_head_assets_reinit_alpine_after_htmx_swap() -> None:
    environment = _env_with_factory()
    html = environment.get_template("app_factory/head_assets.html").render(
        platform_asset_url=lambda name: f"/static/platform/{name}"
    )
    assert "htmx:afterSwap" in html
    assert "Alpine.initTree" in html


def test_grouped_menu_and_htmx_nav_in_sidebar() -> None:
    app = FastAPI()
    environment = _env_with_factory()
    config = PlatformConfig(
        app_name="Ops",
        brand_href="/argus",
        htmx_nav=True,
        menu=(
            MenuGroup(
                "Product",
                (
                    MenuItem("Queue", "/queue", key="queue", use_htmx=True),
                    MenuItem("Docs", "/docs", use_htmx=True),
                ),
            ),
            MenuGroup(
                "Admin",
                (MenuItem("Users", "/admin/users", no_htmx=True),),
            ),
        ),
        paths=PlatformPaths(),
    )
    install_platform(app, environments=[environment], config=config)
    apply_platform_context(environment, config, current_path="/queue")
    html = environment.get_template("page.html").render()
    assert 'id="platform-group-1"' in html or "platform-group-1" in html
    assert "Product" in html and "Admin" in html
    assert 'hx-get="/queue"' in html
    assert 'hx-target="#main-content"' in html
    assert 'data-nav-key="queue"' in html
    assert 'aria-current="page"' in html
    # no_htmx admin link
    assert 'href="/admin/users"' in html
    assert 'hx-get="/admin/users"' not in html


def test_platform_session_partial_is_logout_surface() -> None:
    from jinja2 import ChoiceLoader, DictLoader, Environment, PackageLoader

    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        "account.html": (
                            "{% include 'app_factory/platform_session.html' %}"
                        )
                    }
                ),
                PackageLoader("app_factory", "templates"),
            ]
        ),
        autoescape=True,
    )
    apply_platform_context(env, PlatformConfig(paths=PlatformPaths()))
    html = env.get_template("account.html").render()
    assert "data-platform-session" in html
    assert "Log out" in html
    assert 'action="/logout"' in html
    assert 'data-variant="destructive"' in html



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


def test_shell_boot_template_exports_config_contract() -> None:
    """shell_boot is the shared residual host JS; config keys stay stable."""
    env = Environment(loader=PackageLoader("app_factory", "templates"), autoescape=True)
    html = env.get_template("app_factory/shell_boot.html").render()
    assert "window.appShellConfig" in html
    assert "window.__appShellBooted" in html
    assert "getSidebar" in html
    assert "initBasecoat" in html
    assert "data-sidebar-toggle" in html
    assert "htmx:afterSwap" in html
    assert "htmx:historyCacheHit" in html
    assert "basecoat:sidebar" in html
    assert "app-nav-link--active" in html
    assert "reinitPageScripts" in html
    assert "useDataNavActive" in html


def test_shell_includes_shell_boot_after_head_extra() -> None:
    env = Environment(loader=PackageLoader("app_factory", "templates"), autoescape=True)
    html = env.get_template("app_factory/shell.html").render(
        platform_asset_url=lambda name: f"/static/platform/{name}"
    )
    assert "window.__appShellBooted" in html
    assert html.index("htmx:configRequest") < html.index("window.__appShellBooted")


def test_product_shell_is_full_operator_frame() -> None:
    app = FastAPI()
    env = _env_with_factory()
    config = PlatformConfig(
        app_name="Demo",
        brand_href="/home",
        htmx_nav=True,
        default_hx_swap="innerHTML",
        default_hx_select=None,
        menu=(
            MenuGroup(
                "Main",
                items=(MenuItem("Home", "/home", icon="<i>h</i>"),),
            ),
        ),
        paths=PlatformPaths(),
    )
    install_platform(app, environments=[env], config=config)
    apply_platform_context(env, config, current_path="/home")
    html = env.get_template("page.html").render(page_title="Home")
    assert 'id="app-main"' in html
    assert 'id="main-content"' in html
    assert 'data-page-title="Home"' in html
    assert "app-main-header" in html
    assert "data-platform-theme-locale" in html
    assert "data-platform-foot" in html
    assert 'hx-get="/home"' in html
    assert 'hx-swap="innerHTML"' in html
    # default_hx_select=None → no hx-select on nav items
    nav_chunk = html.split('hx-get="/home"')[1][:240]
    assert "hx-select=" not in nav_chunk
    assert 'href="/home"' in html
