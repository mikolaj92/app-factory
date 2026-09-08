"""Real bundled HTMX: run lifecycle, transport failure and history restore."""

import socket
import threading
import time
from datetime import datetime, timezone

import httpx2
import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright

from fastapi import FastAPI
from jinja2 import Environment, select_autoescape

from app_factory import (
    Run,
    RunError,
    RunPage,
    create_run_router,
    create_run_view_router,
    install_platform,
)


@pytest.fixture
def run_browser():
    class Port:
        run = None
        error = None

        def __init__(self):
            self.reads = []

        async def create_intent(self, scope, intent, *, idempotency_key):
            self.run = Run(
                id="one",
                status="pending",
                created_at=datetime.now(timezone.utc),
                retry_after=1,
            )
            return self.run

        async def get_run(self, scope, run_id):
            self.reads.append(time.monotonic())
            if self.error:
                raise self.error
            return self.run

        async def list_runs(self, scope, *, cursor, limit):
            return RunPage(items=[self.run], next_cursor="next" if not cursor else None)

    port = Port()

    async def authorize(request, action, **kwargs):
        return "alice"

    environment = Environment(autoescape=select_autoescape())
    app = FastAPI()
    install_platform(app, environments=[environment])
    app.include_router(create_run_router(lambda: port, authorize, prefix="/api/runs"))
    app.include_router(
        create_run_view_router(lambda: port, authorize, environment=environment)
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        number = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=number, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{number}"
    try:
        for _ in range(100):
            try:
                if httpx2.get(base + "/openapi.json").status_code == 200:
                    break
            except httpx2.HTTPError:
                pass
            time.sleep(0.05)
        else:
            pytest.fail("Run test server did not start")
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as exc:
                pytest.skip(f"Chromium unavailable: {exc}")
            try:
                page = browser.new_page()
                page.set_default_timeout(8000)
                response = page.request.post(
                    base + "/api/runs",
                    data={"kind": "example"},
                    headers={"Idempotency-Key": "start"},
                )
                assert response.status == 202
                yield page, base, port
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_start_running_terminal_stops_polling(run_browser):
    page, base, port = run_browser
    page.goto(base + "/runs/one")
    expect(page.locator('[data-run-status="pending"]')).to_be_visible()
    port.run = port.run.model_copy(update={"status": "running"})
    expect(page.locator('[data-run-status="running"]')).to_be_visible()
    port.run = port.run.model_copy(update={"status": "succeeded"})
    expect(page.locator('[data-run-status="succeeded"]')).to_be_visible()
    count = len(port.reads)
    page.wait_for_timeout(2200)
    assert len(port.reads) == count
    assert page.locator("#run-detail[hx-trigger]").count() == 0


def test_network_failure_notifies_and_recovers_without_duplicate_pollers(run_browser):
    page, base, port = run_browser
    page.goto(base + "/runs/one")
    page.route("**/runs/one", lambda route: route.abort("internetdisconnected"))
    expect(page.locator("#toaster")).to_contain_text(
        "The request could not be completed"
    )
    expect(page.locator('[data-run-status="pending"]')).to_be_visible()
    page.unroute("**/runs/one")
    port.run = port.run.model_copy(update={"status": "running"})
    expect(page.locator('[data-run-status="running"]')).to_be_visible()
    page.evaluate(
        "() => { for (let i=0; i<5; i++) htmx.process(document.getElementById('run-detail')); }"
    )
    count = len(port.reads)
    page.wait_for_timeout(2200)
    assert 1 <= len(port.reads) - count <= 2
    port.run = port.run.model_copy(update={"status": "failed"})
    expect(page.locator('[data-run-status="failed"]')).to_be_visible()


def test_transient_error_respects_port_backoff(run_browser):
    page, base, port = run_browser
    page.goto(base + "/runs/one")
    port.error = RunError("unavailable", "Temporarily unavailable", retry_after=3)
    expect(page.locator('[data-run-state="transient-error"]')).to_be_visible()
    count = len(port.reads)
    page.wait_for_timeout(1500)
    assert len(port.reads) == count
    port.error = None
    port.run = port.run.model_copy(update={"status": "cancelled"})
    expect(page.locator('[data-run-status="cancelled"]')).to_be_visible()


def test_history_restore_fetches_authorized_shell_and_one_poller(run_browser):
    page, base, port = run_browser
    page.goto(base + "/runs/one")
    # A host navigation link enhances a normal href; exercise HTMX push/back,
    # not a synthetic historyRestore event that would bypass cache-miss logic.
    page.evaluate("""() => {
        const a = document.createElement('a');
        a.textContent = 'History'; a.href = '/runs'; a.id = 'host-history';
        a.setAttribute('hx-get', '/runs'); a.setAttribute('hx-target', 'body');
        a.setAttribute('hx-push-url', 'true');
        document.getElementById('main-content').prepend(a); htmx.process(a);
    }""")
    page.locator("#host-history").click()
    expect(page.locator("#run-history")).to_be_visible()
    count = len(port.reads)
    page.wait_for_timeout(1300)
    assert len(port.reads) == count
    page.go_back()
    expect(page.locator("#sidebar")).to_have_count(1)
    expect(page.locator("#run-detail")).to_have_count(1)
    count = len(port.reads)
    page.wait_for_timeout(2200)
    assert 1 <= len(port.reads) - count <= 2
    port.run = port.run.model_copy(update={"status": "succeeded"})
    expect(page.locator('[data-run-status="succeeded"]')).to_be_visible()
    count = len(port.reads)
    page.wait_for_timeout(1300)
    assert len(port.reads) == count
