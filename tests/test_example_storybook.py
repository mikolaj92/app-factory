"""Smoke contracts for the local chrome storybook."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from example.app import app

client = TestClient(app)


def _chunk(html: str, marker: str, size: int = 1800) -> str:
    start = html.find(marker)
    if start == -1:
        return ""
    return html[start : start + size]


def test_catalog_and_core_stories_render() -> None:
    for path in (
        "/",
        "/stories/guest",
        "/stories/signed-in",
        "/stories/bare",
        "/stories/client",
        "/stories/account",
        "/stories/htmx",
        "/stories/htmx/b",
        "/stories/locales",
        "/stories/components",
        "/stories/login",
        "/stories/register",
        "/stories/admin-users",
        "/stories/account-management",
        "/stories/activation?capability=example",
        "/stories/recovery?capability=example",
        "/stories/credentials",
        "/stories/denied",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "basecoat-factory.min.css" in response.text
        assert 'id="main-content"' in response.text


@pytest.mark.parametrize(
    ("path", "uses_product_shell"),
    (
        ("/stories/login", False),
        ("/stories/activation?capability=example", False),
        ("/stories/account", True),
        ("/stories/credentials", True),
        ("/stories/admin-users", True),
    ),
)
def test_auth_surfaces_load_same_origin_platform_stack(
    path: str, uses_product_shell: bool
) -> None:
    html = client.get(path).text
    for asset_path in (
        "/static/platform/basecoat-factory.min.css",
        "/static/platform/basecoat-js.min.js",
        "/static/platform/htmx.min.js",
        "/static/platform/alpine.min.js",
    ):
        assert asset_path in html
    assert "unpkg.com" not in html
    assert "cdn.jsdelivr.net" not in html
    assert ('id="sidebar"' in html) is uses_product_shell


def test_guest_chrome_foot_vs_header() -> None:
    html = client.get("/stories/guest").text
    foot = _chunk(html, "data-platform-foot")
    header = _chunk(html, "app-main-header__controls")

    assert "data-platform-auth" in foot
    assert 'href="/stories/login"' in foot
    assert 'href="/stories/register"' in foot
    assert "Login" in foot
    assert "Create account" in foot
    assert "data-theme-toggle" not in foot
    assert "data-platform-account-link" not in foot
    assert "platform-avatar" not in foot
    assert 'action="/stories/logout"' not in html

    assert "data-platform-theme-locale" in header
    assert "data-theme-toggle" in header
    assert "data-platform-locale-picker" in header
    assert "data-platform-account-link" not in header
    assert "Ada Lovelace" not in html
    assert "data-platform-session" not in html
    assert 'id="sidebar"' in html
    assert "data-sidebar-toggle" in html


def test_signed_in_chrome_foot_vs_header() -> None:
    html = client.get("/stories/signed-in").text
    foot = _chunk(html, "data-platform-foot")
    header_start = html.find("app-main-header__controls")
    header = html[header_start : html.find("</header>", header_start)]

    assert "data-platform-auth" in foot
    assert "data-platform-account-link" in foot
    assert "platform-avatar" in foot
    assert "Ada Lovelace" in foot
    assert 'href="/stories/login"' not in foot
    assert "data-theme-toggle" not in foot
    assert 'action="/stories/logout"' not in foot

    assert "data-theme-toggle" in header
    assert "data-platform-locale-picker" in header
    assert "data-platform-account-link" not in header
    assert "platform-avatar" not in header
    assert "Ada Lovelace" not in header
    assert "data-platform-session" not in html
    assert 'action="/stories/logout"' not in html


def test_account_is_only_logout_surface() -> None:
    signed = client.get("/stories/signed-in").text
    account = client.get("/stories/account").text

    assert "data-platform-session" not in signed
    assert 'action="/stories/logout"' not in signed

    assert "data-platform-session" in account
    assert "Log out" in account
    assert 'action="/stories/logout"' in account
    # Logout stays on the account surface, not in sidebar foot chrome.
    foot = _chunk(account, "data-platform-foot")
    assert 'action="/stories/logout"' not in foot


def test_bare_shell_has_no_product_sidebar() -> None:
    html = client.get("/stories/bare").text
    assert 'id="sidebar"' not in html
    assert "data-platform-foot" not in html
    assert "data-platform-auth" not in html
    assert "data-platform-theme-locale" in html
    assert "data-theme-toggle" in html
    assert "app-main-header" in html


def test_client_shell_is_slim_basecoat_without_htmx_alpine() -> None:
    html = client.get("/stories/client").text
    assert "data-platform-client" in html
    assert "app-client" in html
    assert 'id="sidebar"' not in html
    assert "data-platform-controls" in html
    assert "data-platform-theme-locale" in html
    assert "data-platform-auth" in html
    assert "data-platform-session" in html
    assert "/static/platform/basecoat-factory.min.css" in html
    assert "/static/platform/basecoat-js.min.js" in html
    assert "/static/platform/htmx.min.js" not in html
    assert "/static/platform/alpine.min.js" not in html
    assert "htmx:configRequest" not in html
    assert "Alpine.initTree" not in html


def test_theme_and_locale_stay_in_header_not_foot() -> None:
    for path in ("/stories/guest", "/stories/signed-in", "/stories/account", "/"):
        html = client.get(path).text
        foot = _chunk(html, "data-platform-foot")
        header = _chunk(html, "app-main-header__controls")
        assert "data-theme-toggle" not in foot, path
        assert "data-platform-locale-picker" not in foot, path
        assert "data-theme-toggle" in header, path
        assert "data-platform-locale-picker" in header, path


def test_catalog_exposes_native_host_controls() -> None:
    html = client.get("/").text
    assert "data-demo-host-link" in html
    assert "data-demo-host-form" in html
    assert 'hx-post="/stories/demo-form"' in html
    assert 'id="demo-form-result"' in html


def test_account_management_story_composes_library_owned_surfaces() -> None:
    response = client.get("/stories/account-management")
    assert response.status_code == 200
    for path in (
        "/stories/activation?capability=example",
        "/stories/recovery?capability=example",
        "/stories/credentials",
        "/stories/admin-users",
    ):
        assert f'href="{path}"' in response.text
    assert "<code>/account/sessions</code>" in response.text
    assert "<code>/admin/audit</code>" in response.text
    assert "my-auth + my-usermanager" in response.text
    assert "data-platform-identity-authenticated" in response.text


def test_admin_users_story_when_enabled() -> None:
    response = client.get("/stories/admin-users")
    assert response.status_code == 200
    assert "Users & invitations" in response.text
    assert "Ada Lovelace" in response.text
    assert "data-platform-identity-authenticated" in response.text
    assert "data-platform-session" not in response.text


def test_platform_assets_mounted() -> None:
    css = client.get("/static/platform/basecoat-factory.min.css")
    assert css.status_code == 200
    assert len(css.content) > 100_000
    assert b".app-stack" in css.content
    assert b".btn" in css.content


def test_demo_form_accepts_post() -> None:
    response = client.post("/stories/demo-form", data={"message": "hello"})
    assert response.status_code == 200
    assert "Submitted: hello" in response.text
    assert "data-demo-form-result" in response.text


def test_locale_flags_are_real_emoji() -> None:
    response = client.get("/stories/locales")
    assert response.status_code == 200
    # PL / GB / DE regional-indicator pairs (not mojibake)
    assert "\U0001f1f5\U0001f1f1" in response.text
    assert "\U0001f1ec\U0001f1e7" in response.text
    assert "\U0001f1e9\U0001f1ea" in response.text
