"""Real bundled HTMX must show errors without trusting proxy HTML."""

import pytest

from jinja2 import Environment
from app_factory import configure_jinja_env
from test_browser_chrome import browser_page, live_server  # noqa: F401


@pytest.mark.parametrize("status", [403, 422, 500])
@pytest.mark.parametrize("method", ["post", "patch", "delete"])
def test_htmx_mutation_errors_are_visible_without_swapping_raw_html(
    browser_page, status, method  # noqa: F811
):
    page, base = browser_page
    env = configure_jinja_env(Environment(autoescape=True))
    html = (
        '<html><head><script src="/static/platform/htmx.min.js"></script></head><body>'
        + env.get_template("app_factory/toast_boot.html").render()
        + f'<form hx-{method}="/error" hx-target="#result"><button>Submit</button></form>'
        '<div id="result">Original</div></body></html>'
    )
    page.route(
        "**/error-page",
        lambda route: route.fulfill(body=html, content_type="text/html"),
    )
    page.route(
        "**/error",
        lambda route: route.fulfill(
            status=status,
            content_type="text/html",
            body="<script>window.secretLeak = true</script><h1>SECRET proxy traceback</h1>",
        ),
    )
    try:
        page.goto(base + "/error-page")
        page.get_by_role("button", name="Submit", exact=True).click()
        page.wait_for_function(
            "document.querySelector('#result [role=alert]') !== null"
        )
        assert (
            page.locator("#result [role=alert]").inner_text()
            == "The request could not be completed. Try again."
        )
        assert "Original" in page.locator("#result").inner_text()
        assert "SECRET" not in page.locator("body").inner_text()
        assert page.evaluate("window.secretLeak") is None
        page.get_by_role("button", name="Submit", exact=True).click()
        page.wait_for_load_state("networkidle")
        assert page.locator("#result [role=alert]").count() == 1
    finally:
        page.unroute("**/error-page")
        page.unroute("**/error")
