import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jinja2 import Environment
from playwright.sync_api import sync_playwright

from app_factory.jinja import configure_jinja_env

env = configure_jinja_env(Environment(autoescape=True))
markup = env.from_string("""{% from "app_factory/components/file_upload.html" import file_upload, file_upload_field %}
{{ file_upload(id="one", action="/upload", accept=".txt", max_bytes=4, multiple=true, target="#result", extra_form_attrs='novalidate') }}
{{ file_upload(id="two", action="/upload", required=false, target="#result") }}
<div id="result"></div>
<script src="/htmx.js"></script>
{% include "app_factory/file_upload_boot.html" %}
""").render()
received = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = (
            Path("app_factory/assets/htmx.min.js").read_bytes()
            if self.path == "/htmx.js"
            else markup.encode()
        )
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/javascript" if self.path == "/htmx.js" else "text/html",
        )
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        received.append(
            self.rfile.read(int(self.headers.get("Content-Length", 0))).decode(
                errors="replace"
            )
        )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
results = []
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    context = browser.new_context()
    page = context.new_page()
    requests = []
    page.on(
        "request",
        lambda req: requests.append(req.url) if req.method == "POST" else None,
    )
    answer = [True]
    page.on("dialog", lambda dialog: dialog.accept() if answer[0] else dialog.dismiss())

    def fresh():
        page.goto(f"http://127.0.0.1:{server.server_port}")
        page.wait_for_function(
            'document.querySelector("[data-app-file-upload-field]").dataset.appFileUploadReady === "true"'
        )

    def files(names=("ok.txt",), size=4, selector="#one-input"):
        page.locator(selector).set_input_files(
            [
                {"name": name, "mimeType": "text/plain", "buffer": b"x" * size}
                for name in names
            ]
        )

    def run(name, expected, action):
        before = (len(requests), len(received))
        action()
        page.wait_for_timeout(300)
        actual = (len(requests) - before[0], len(received) - before[1])
        busy = page.locator("#one [data-app-file-submit]").get_attribute("aria-busy")
        assert actual == (expected, expected), (name, actual)
        assert busy is None, (name, "busy")
        assert page.locator("#one [data-app-file-progress]").is_hidden(), name
        results.append(
            {"scenario": name, "browser_POST": actual[0], "server_POST": actual[1]}
        )

    fresh()
    run(
        "required empty ajax",
        0,
        lambda: page.evaluate(
            'htmx.ajax("POST", "/upload", {source: document.querySelector("#one"), target: "#result"})'
        ),
    )
    assert (
        page.locator("#one [data-app-file-status]").inner_text()
        == "Choose at least one file."
    )
    files(("bad.bin",))
    run(
        "wrong type native trigger",
        0,
        lambda: page.locator("#one button[type=submit]").click(),
    )
    assert "not accepted" in page.locator("#one [data-app-file-status]").inner_text()
    files(size=5)
    run(
        "oversized ajax",
        0,
        lambda: page.evaluate(
            'htmx.ajax("POST", "/upload", {source: document.querySelector("#one"), target: "#result"})'
        ),
    )
    assert "size limit" in page.locator("#one [data-app-file-status]").inner_text()
    files()
    run(
        "exact limit single",
        1,
        lambda: page.locator("#one button[type=submit]").click(),
    )
    run(
        "optional empty other form",
        1,
        lambda: page.locator("#two button[type=submit]").click(),
    )
    files(("a.txt", "b.txt"))
    answer[0] = False
    run("batch refused", 0, lambda: page.locator("#one button[type=submit]").click())
    answer[0] = True
    run("batch accepted", 1, lambda: page.locator("#one button[type=submit]").click())
    assert 'name="confirmed_count"\r\n\r\n2' in received[-1]
    for boundary in ("htmx:config:request", "htmx:before:request"):
        for capture in (True, False):
            fresh()
            answer[0] = True
            files(("a.txt", "b.txt"))
            page.evaluate(
                """({boundary, capture}) => {
                window.cancel = event => { event.preventDefault(); window.saved = event.detail.ctx; };
                document.addEventListener(boundary, window.cancel, capture);
            }""",
                {"boundary": boundary, "capture": capture},
            )
            run(
                f"host cancel {boundary} capture={capture}",
                0,
                lambda: page.locator("#one button[type=submit]").click(),
            )
            page.evaluate(
                "(args) => document.removeEventListener(args.boundary, window.cancel, args.capture)",
                {"boundary": boundary, "capture": capture},
            )
            answer[0] = False
            run(
                "confirmed host replay",
                1,
                lambda: page.evaluate('document.querySelector("#one").requestSubmit()'),
            )
            files(("bad.bin",))
            run(
                "changed invalid replay",
                0,
                lambda: page.evaluate('document.querySelector("#one").requestSubmit()'),
            )
    fresh()
    files()
    page.evaluate("""() => {
      const button = document.createElement('button'); button.type = 'button'; button.id = 'child';
      button.setAttribute('hx-post', '/upload'); button.setAttribute('hx-target', '#result');
      document.querySelector('#one').append(button); htmx.process(button);
    }""")
    files(("bad.bin",))
    run("unrelated child request", 1, lambda: page.locator("#child").click())
    fresh()
    page.evaluate("""() => {
      const field = document.querySelector('#one [data-app-file-upload-field]').cloneNode(true);
      delete field.dataset.appFileUploadReady;
      field.querySelector('input').id = 'extra';
      document.querySelector('#one').append(field);
      document.dispatchEvent(new CustomEvent('htmx:after:swap', {detail: {ctx: {target: field}}}));
    }""")
    files()
    assert page.locator("#one button[type=submit]").is_disabled()
    files(("bad.bin",), selector="#extra")
    run(
        "second field invalid",
        0,
        lambda: page.locator("#one button[type=submit]").click(),
    )
    files(selector="#extra")
    answer[0] = True
    for _ in range(3):
        page.evaluate(
            'document.dispatchEvent(new CustomEvent("htmx:after:swap", {detail: {ctx: {target: document.querySelector("#one")}}}))'
        )
    run(
        "multiple fields repeated init",
        1,
        lambda: page.locator("#one button[type=submit]").click(),
    )
    fresh()
    page.evaluate("""() => {
      const data = new DataTransfer(); data.items.add(new File(['xxxx'], 'drop.txt', {type:'text/plain'}));
      document.querySelector('#one [data-app-file-dropzone]').dispatchEvent(new DragEvent('drop', {bubbles:true, cancelable:true, dataTransfer:data}));
    }""")
    assert page.locator("#one [data-app-file-list]").inner_text().startswith("drop.txt")
    page.locator("#one [data-app-file-list] button").click()
    assert page.locator("#one-input").evaluate("(input) => input.files.length") == 0
    results.append({"scenario": "drop and removal", "result": "passed"})
    fresh()
    files()
    page.route("**/upload", lambda route: route.abort())
    page.locator("#one button[type=submit]").click()
    page.wait_for_timeout(300)
    assert (
        page.locator("#one [data-app-file-submit]").get_attribute("aria-busy") is None
    )
    page.unroute("**/upload")
    run(
        "retry after network failure",
        1,
        lambda: page.locator("#one button[type=submit]").click(),
    )
    page.route("**/upload", lambda route: route.fulfill(status=500, body="error"))
    page.locator("#one button[type=submit]").click()
    page.wait_for_timeout(300)
    assert page.locator("#one [data-app-file-progress]").is_hidden()
    page.unroute("**/upload")
    run(
        "retry after HTTP failure",
        1,
        lambda: page.locator("#one button[type=submit]").click(),
    )
    fresh()
    files()
    page.evaluate(
        """() => { const form = document.querySelector('#one'); form.removeAttribute('hx-post'); htmx.process(form); }"""
    )
    run(
        "native multipart without HTMX",
        1,
        lambda: page.locator("#one button[type=submit]").click(),
    )
    context.close()
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    page.goto(f"http://127.0.0.1:{server.server_port}")
    files()
    before = len(received)
    page.locator("#one button[type=submit]").click()
    page.wait_for_load_state()
    assert len(received) == before + 1
    results.append({"scenario": "no JavaScript multipart", "server_POST": 1})
    browser.close()
server.shutdown()
Path(".runtime/upload-checks/upload-results.json").write_text(
    json.dumps(results, indent=2)
)
print(json.dumps(results, indent=2))
