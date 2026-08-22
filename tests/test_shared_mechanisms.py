from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from jinja2 import Environment

from app_factory import SessionCsrfProtection, htmx_redirect
from app_factory.jinja import configure_jinja_env


def _request(scope: dict[str, object]) -> Request:
    return Request(
        {"type": "http", "method": "GET", "path": "/", "headers": [], **scope}
    )


def test_htmx_redirect_keeps_native_location_and_adds_full_page_header() -> None:
    app = FastAPI()

    @app.post("/go")
    def go(request: Request):
        return htmx_redirect(request, "/target?ok=1#done")

    client = TestClient(app)
    native = client.post("/go", follow_redirects=False)
    htmx = client.post("/go", headers={"HX-Request": "true"}, follow_redirects=False)
    assert native.status_code == htmx.status_code == 303
    assert native.headers["location"] == htmx.headers["location"] == "/target?ok=1#done"
    assert "HX-Redirect" not in native.headers
    assert htmx.headers["HX-Redirect"] == "/target?ok=1#done"


def test_htmx_redirect_rejects_empty_url() -> None:
    with pytest.raises(ValueError, match="url"):
        htmx_redirect(_request({}), "")


def test_session_csrf_mints_reuses_and_validates_token() -> None:
    csrf = SessionCsrfProtection(session_key="test_csrf")
    request = _request({"session": {}})
    first = csrf.token(request)
    second = csrf.token(request)
    assert first == second
    csrf.validate(request, first)
    with pytest.raises(PermissionError):
        csrf.validate(request, "wrong")


def test_session_csrf_requires_session_middleware() -> None:
    with pytest.raises(RuntimeError, match="SessionMiddleware"):
        SessionCsrfProtection().token(_request({}))


def test_pagination_is_native_htmx_accessible_and_encodes_query() -> None:
    env = configure_jinja_env(Environment(autoescape=True))
    template = env.from_string(
        '{% from "app_factory/components/pagination.html" import pagination %}'
        '{{ pagination(3, 8, "/items", query_params={"q": "legal work", "page": 99}, '
        'hx_target="#results", hx_push_url=true, previous_label="Wstecz", next_label="Dalej") }}'
    )
    html = template.render()
    assert 'aria-label="Pagination"' in html
    assert 'aria-current="page">3</a>' in html
    assert 'href="/items?q=legal%20work&amp;page=2"' in html
    assert 'hx-get="/items?q=legal%20work&amp;page=4"' in html
    assert 'hx-target="#results"' in html
    assert 'hx-push-url="true"' in html
    assert "page=99" not in html


def test_toast_boot_is_opt_in_and_handles_network_failures_once() -> None:
    env = configure_jinja_env(Environment(autoescape=True))
    slim = env.get_template("app_factory/shell.html").render()
    enabled = env.get_template("app_factory/shell.html").render(
        toast_enabled=True,
        network_error_message="Offline",
    )
    assert 'id="toaster"' not in slim
    assert 'id="toaster"' in enabled
    assert "window.__appToastBooted" in enabled
    assert "htmx:sendError" in enabled
    assert "htmx:timeout" in enabled
    assert "Offline" in enabled
