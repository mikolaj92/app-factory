"""Smoke contracts for the local chrome storybook."""

from __future__ import annotations

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
        "/stories/account",
        "/stories/htmx",
        "/stories/htmx/b",
        "/stories/locales",
        "/stories/components",
        "/stories/login",
        "/stories/register",
        "/stories/admin-users",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "basecoat-factory.min.css" in response.text
        assert 'id="main-content"' in response.text


def test_guest_chrome_foot_vs_header() -> None:
    html = client.get("/stories/guest").text
    foot = _chunk(html, "data-platform-foot")
    header = _chunk(html, "app-main-header__controls")

    assert "data-platform-auth" in foot
    assert 'href="/stories/login"' in foot
    assert 'href="/stories/register"' in foot
    assert "Login" in foot
    assert "Register" in foot
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
    header = _chunk(html, "app-main-header__controls")

    # Identity lives in sidebar foot, not header chrome.
    assert "data-platform-account-link" in foot
    assert "platform-avatar" in foot
    assert "Ada Lovelace" in foot
    assert "data-platform-auth" not in foot
    assert 'href="/stories/login"' not in foot
    assert "data-theme-toggle" not in foot
    assert 'action="/stories/logout"' not in foot

    assert "data-theme-toggle" in header
    assert "data-platform-locale-picker" in header
    assert "data-platform-account-link" not in header
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


def test_admin_users_story_when_enabled() -> None:
    response = client.get("/stories/admin-users")
    assert response.status_code == 200
    assert "Admin users stub" in response.text
    assert "Ada Lovelace" in response.text
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
