"""Optional real-browser chrome isolation (issue #9).

Default suite stays dep-free. These tests skip unless Playwright + Chromium
are available (``uv sync --extra browser && uv run playwright install chromium``).
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import httpx2
import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

from starlette.applications import Starlette
from starlette.routing import Mount

from example.app import app

# Exercise the same installed app both at its normal origin and behind the
# reverse-proxy style mount used by consumers. The package's absolute static
# asset URL remains root-relative while document-relative CSS imports reveal
# the mount prefix in the failing request path.
browser_app = Starlette(routes=[Mount("/argus", app), Mount("/", app)])


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def live_server() -> Iterator[str]:
    port = _free_port()
    config = uvicorn.Config(
        browser_app,
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
            with httpx2.Client(base_url=base, timeout=0.5) as client:
                if client.get("/").status_code == 200:
                    break
        except httpx2.HTTPError:
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
        except Exception as exc:  # noqa: BLE001  # pragma: no cover - env dependent
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


def test_host_can_use_a_tailwind_class_outside_the_old_safelist(browser_page) -> None:
    page, base = browser_page
    page.goto(f"{base}/")
    page.wait_for_function(
        "() => Boolean(document.querySelector('script[src*=\"tailwind.min.js\"]'))"
    )
    page.evaluate(
        """() => {
          const el = document.createElement('div');
          el.id = 'tw-probe';
          el.className = 'gap-7';
          document.body.appendChild(el);
        }"""
    )
    page.wait_for_function(
        "() => getComputedStyle(document.getElementById('tw-probe')).gap === '28px'"
    )


@pytest.mark.parametrize("path", ["/", "/argus/"])
def test_tailwind_virtual_imports_stay_same_origin_and_no_preflight(
    browser_page, path: str
) -> None:
    page, base = browser_page
    requests: list[str] = []
    failed: list[str] = []
    responses: list[tuple[str, int]] = []
    console_errors: list[str] = []
    page.on("request", lambda request: requests.append(request.url))
    page.on("requestfailed", lambda request: failed.append(request.url))
    page.on(
        "response",
        lambda response: responses.append((response.url, response.status)),
    )
    page.on(
        "console",
        lambda message: (
            console_errors.append(message.text) if message.type == "error" else None
        ),
    )

    page.goto(f"{base}{path}")
    page.wait_for_function(
        "() => Boolean(document.querySelector('script[src*=\"tailwind.min.js\"]'))"
    )
    page.wait_for_function(
        "() => document.querySelectorAll('style:not([type=\"text/tailwindcss\"])').length >= 1"
    )

    virtual_imports = ("/tailwindcss/theme", "/tailwindcss/utilities")
    tailwind_asset_url = f"{base}/static/platform/tailwind.min.js"
    assert tailwind_asset_url in requests
    assert (tailwind_asset_url, 200) in responses
    assert not [
        url for url in requests if any(url_path in url for url_path in virtual_imports)
    ]
    assert not [
        url for url in failed if any(url_path in url for url_path in virtual_imports)
    ]
    assert not any("Failed to load resource" in error for error in console_errors)

    generated_css = page.locator(
        'style:not([type="text/tailwindcss"])'
    ).first.text_content()
    assert generated_css is not None
    assert "@layer base" not in generated_css

    page.evaluate(
        """() => {
          const el = document.createElement('div');
          el.id = 'tailwind-virtual-import-probe';
          el.className = 'flex gap-7 text-red-500 bg-background';
          document.body.appendChild(el);
        }"""
    )
    page.wait_for_function(
        """() => {
          const style = getComputedStyle(document.getElementById('tailwind-virtual-import-probe'));
          return style.display === 'flex'
            && style.gap === '28px'
            && style.color === 'oklch(0.637 0.237 25.331)'
            && style.backgroundColor !== 'rgba(0, 0, 0, 0)';
        }"""
    )
