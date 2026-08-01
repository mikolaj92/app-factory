"""Optional real-browser chrome isolation (issue #9).

Default suite stays dep-free. These tests skip unless Playwright + Chromium
are available (``uv sync --extra browser && uv run playwright install chromium``).
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

from example.app import app  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def live_server() -> Iterator[str]:
    port = _free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 10
    while time.time() < deadline:
        if server.should_exit:
            break
        try:
            with httpx.Client(base_url=base, timeout=0.5) as client:
                if client.get("/").status_code == 200:
                    break
        except Exception:
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=2)
        pytest.skip("uvicorn test server failed to become ready")

    try:
        yield base
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser_page(live_server: str):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - env dependent
            pytest.skip(f"chromium unavailable: {exc}")
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(8_000)
        try:
            yield page, live_server
        finally:
            context.close()
            browser.close()


def test_theme_toggle_does_not_submit_host_form(browser_page) -> None:
    page, base = browser_page
    posts: list[str] = []

    def on_request(request) -> None:
        if request.method == "POST":
            posts.append(request.url)

    page.on("request", on_request)
    page.goto(f"{base}/")
    page.locator("[data-demo-host-form]").wait_for()
    page.get_by_role("button", name="Toggle theme").click()
    page.wait_for_timeout(250)
    assert posts == [], f"theme toggle caused POSTs: {posts}"
    assert page.locator("#demo-form-result").inner_text().strip() == ""

    page.locator("#demo-message").fill("from-browser")
    page.get_by_role("button", name="Submit host form").click()
    page.locator("[data-demo-form-result]").wait_for()
    assert "Submitted: from-browser" in page.locator("#demo-form-result").inner_text()


def test_htmx_nav_keeps_sidebar_and_reinits_alpine(browser_page) -> None:
    page, base = browser_page
    page.goto(f"{base}/stories/htmx")
    page.locator("[data-panel-label]").wait_for()
    assert page.locator("#sidebar").count() == 1
    assert page.locator("[data-panel-label]").inner_text().strip() == "A"

    page.locator("[data-alpine-count]").wait_for()
    page.get_by_role("button", name="Increment").click()
    page.wait_for_function(
        "() => document.querySelector('[data-alpine-count]')?.textContent === '1'"
    )

    # Real HTMX sidebar nav (hx-get + hx-select #main-content), not plain Panel B hrefs.
    page.locator('#sidebar a[data-nav-key="htmx-b"]').click()
    page.wait_for_function(
        "() => document.querySelector('[data-panel-label]')?.textContent === 'B'"
    )
    assert page.locator("#sidebar").count() == 1

    # Fresh Alpine tree after swap: counter resets and increments once per click.
    page.wait_for_function(
        "() => document.querySelector('[data-alpine-count]')?.textContent === '0'"
    )
    page.get_by_role("button", name="Increment").click()
    page.wait_for_function(
        "() => document.querySelector('[data-alpine-count]')?.textContent === '1'"
    )
    page.get_by_role("button", name="Increment").click()
    page.wait_for_function(
        "() => document.querySelector('[data-alpine-count]')?.textContent === '2'"
    )
