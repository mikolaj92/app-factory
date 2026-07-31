"""Smoke contracts for the local chrome storybook."""

from __future__ import annotations

from starlette.testclient import TestClient

from example.app import app


client = TestClient(app)


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
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "basecoat-factory.min.css" in response.text
        assert 'id="main-content"' in response.text


def test_guest_vs_signed_in_chrome() -> None:
    guest = client.get("/stories/guest")
    assert 'data-platform-auth' in guest.text
    assert 'href="/stories/login"' in guest.text
    assert "Ada Lovelace" not in guest.text

    signed = client.get("/stories/signed-in")
    assert "Ada Lovelace" in signed.text
    assert 'href="/stories/login"' not in signed.text
    assert 'data-platform-session' not in signed.text
    assert 'action="/stories/logout"' not in signed.text


def test_account_is_logout_surface() -> None:
    response = client.get("/stories/account")
    assert response.status_code == 200
    assert "data-platform-session" in response.text
    assert "Log out" in response.text


def test_platform_assets_mounted() -> None:
    css = client.get("/static/platform/basecoat-factory.min.css")
    assert css.status_code == 200
    assert len(css.content) > 100


def test_demo_form_accepts_post() -> None:
    response = client.post("/stories/demo-form", data={"message": "hello"})
    assert response.status_code == 200
    assert "Submitted: hello" in response.text
