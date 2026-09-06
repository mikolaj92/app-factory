from datetime import datetime, timezone
from html.parser import HTMLParser

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment
import pytest

from app_factory import Run, RunIntent, configure_jinja_env


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("type") == "hidden":
            self.values[attrs["name"]] = attrs.get("value", "")


class Csrf:
    def token(self, request):
        return "session-token"

    def validate(self, request, submitted_token):
        if submitted_token != self.token(request):
            raise PermissionError("invalid csrf token")


def make_host(*, files=None, builder=None, csrf=None):
    from app_factory import IntakeField, IntakeSpec, create_intake_router

    calls = []
    runs = {}

    class Port:
        async def create_intent(self, scope, intent, *, idempotency_key):
            from app_factory import RunError

            calls.append((scope, intent, idempotency_key))
            key = scope, idempotency_key
            if key in runs and runs[key][0] != intent:
                raise RunError("conflict", "Key reused with different inputs")
            if key not in runs:
                runs[key] = (
                    intent,
                    Run(
                        id=f"run-{len(runs) + 1}",
                        status="pending",
                        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    ),
                )
            return runs[key][1]

    async def authorize(request, action, *, run_id=None, intent=None):
        from app_factory import RunError

        if request.headers.get("X-Deny"):
            raise RunError("forbidden", "Access denied")
        return request.headers.get("X-Owner", "alice")

    async def build(request, scope, submission):
        if builder:
            return await builder(request, scope, submission)
        return RunIntent(
            kind="example",
            input={
                **submission.fields,
                "files": [f.filename for f in submission.files],
            },
        )

    spec = IntakeSpec(
        fields=(
            IntakeField(name="title", label="Title", required=True, max_length=20),
            IntakeField(
                name="mode",
                label="Mode",
                kind="select",
                options=(("a", "A"), ("b", "B")),
            ),
        ),
        files=files,
    )
    app = FastAPI()
    app.include_router(
        create_intake_router(
            lambda: Port(),
            authorize,
            build,
            spec=spec,
            environment=configure_jinja_env(Environment(autoescape=True)),
            csrf=csrf or Csrf(),
            run_url=lambda request, run: f"/results/{run.id}",
        )
    )
    return TestClient(app), calls, runs


def test_session_csrf_is_bound_to_browser_session():
    from app_factory import SessionCsrfProtection
    from starlette.middleware.sessions import SessionMiddleware

    client, calls, _ = make_host(csrf=SessionCsrfProtection())
    client.app.add_middleware(SessionMiddleware, secret_key="test-only-secret")
    data = {**Inputs(client.get("/intake").text).values, "title": "Example"}
    response = client.post("/intake", data=data, follow_redirects=False)
    assert response.status_code == 303
    client.cookies.clear()
    rejected = client.post("/intake", data=data)
    assert rejected.status_code == 403 and len(calls) == 1


def test_same_key_in_different_scopes_creates_independent_runs():
    client, calls, runs = make_host()
    data = {**Inputs(client.get("/intake").text).values, "title": "Example"}
    for owner in ["alice", "bob"]:
        response = client.post(
            "/intake", data=data, headers={"HX-Request": "true", "X-Owner": owner}
        )
        assert response.status_code == 200
    assert len(runs) == 2 and [call[0] for call in calls] == ["alice", "bob"]


def test_text_intake_retries_return_receipt_and_native_post_redirects():
    client, calls, runs = make_host()
    page = client.get("/intake")
    assert page.status_code == 200
    assert 'method="post"' in page.text
    assert 'hx-target="#intake"' in page.text
    assert 'type="file"' not in page.text
    data = {**Inputs(page.text).values, "title": "Example", "mode": "b"}
    first = client.post("/intake", data=data, headers={"HX-Request": "true"})
    retry = client.post("/intake", data=data, headers={"HX-Request": "true"})
    assert first.status_code == retry.status_code == 200
    assert first.text == retry.text
    assert 'id="intake-status"' in first.text
    assert 'id="intake"' in first.text
    assert "run-1" in first.text and "Example" in first.text and "B" in first.text
    assert "$store" not in page.text
    native = client.post("/intake", data=data, follow_redirects=False)
    assert native.status_code == 303
    assert native.headers["location"] == "/results/run-1"
    assert len(runs) == 1 and len(calls) == 3


@pytest.mark.parametrize("htmx", [False, True])
@pytest.mark.parametrize(
    "change,message",
    [
        ({"title": ""}, "This field is required"),
        ({"title": "x" * 21}, "Use at most 20 characters"),
        ({"mode": "unknown"}, "Choose a listed option"),
        ({"idempotency_key": " "}, "Invalid submission key"),
        ({"csrf_token": "bad"}, "Invalid CSRF token"),
        ({"extra": "unexpected"}, "Unexpected or repeated inputs"),
    ],
)
def test_mechanical_errors_render_without_start(change, message, htmx):
    client, calls, _ = make_host()
    data = {
        **Inputs(client.get("/intake").text).values,
        "title": "Example",
        "mode": "a",
        **change,
    }
    response = client.post(
        "/intake", data=data, headers={"HX-Request": str(htmx).lower()}
    )
    assert response.status_code == (
        200 if htmx else (403 if "csrf_token" in change else 422)
    )
    assert message in response.text
    assert 'role="alert"' in response.text
    assert 'id="intake"' in response.text
    if "title" in change or "mode" in change:
        assert 'aria-invalid="true"' in response.text
        field = "title" if "title" in change else "mode"
        assert f'aria-describedby="intake-{field}-error"' in response.text
    assert not calls


def test_domain_errors_preserve_text_and_key_and_escape_messages():
    from app_factory import IntakeError

    async def build(request, scope, submission):
        raise IntakeError({"title": "<invalid title>", "": "Please correct the form"})

    client, calls, _ = make_host(builder=build)
    data = {
        **Inputs(client.get("/intake").text).values,
        "title": "Example",
        "mode": "b",
    }
    response = client.post("/intake", data=data, headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert 'value="Example"' in response.text and 'value="b" selected' in response.text
    assert Inputs(response.text).values["idempotency_key"] == data["idempotency_key"]
    assert "&lt;invalid title&gt;" in response.text
    assert "Please correct the form" in response.text
    assert not calls


def test_authorization_denial_and_key_conflict_are_form_errors():
    client, calls, _ = make_host()
    data = {**Inputs(client.get("/intake").text).values, "title": "Example"}
    denied = client.post("/intake", data=data, headers={"X-Deny": "yes"})
    assert denied.status_code == 403 and "Access denied" in denied.text
    assert not calls
    client.post("/intake", data=data, headers={"HX-Request": "true"})
    conflict = client.post("/intake", data={**data, "title": "Changed"})
    assert conflict.status_code == 409 and "Key reused" in conflict.text


@pytest.mark.parametrize("count", [0, 1, 2])
def test_optional_uploads_use_existing_field_and_bounded_bytes(count):
    from app_factory import IntakeFiles

    submissions = []

    async def build(request, scope, submission):
        submissions.append(submission)
        # A real host stores files idempotently and returns stable refs here.
        return RunIntent(
            kind="example", input={"refs": [f.filename for f in submission.files]}
        )

    client, calls, runs = make_host(files=IntakeFiles(max_files=2), builder=build)
    page = client.get("/intake")
    assert "data-app-file-upload-field" in page.text
    assert "multiple" in page.text
    data = {**Inputs(page.text).values, "title": "Example"}
    files = [("files", (f"file-{i}.txt", b"abc", "text/plain")) for i in range(count)]
    response = client.post(
        "/intake", data=data, files=files, headers={"HX-Request": "true"}
    )
    retry = client.post(
        "/intake", data=data, files=files, headers={"HX-Request": "true"}
    )
    assert response.status_code == 200 and response.text == retry.text
    assert len(runs) == 1 and len(submissions[0].files) == count
    assert submissions[0].idempotency_key == data["idempotency_key"]
    for upload in submissions[0].files:
        assert upload.data == b"abc"
        assert upload.content_type == "text/plain"
        assert upload.filename in response.text


@pytest.mark.parametrize(
    "config,uploads,message",
    [
        ({"required": True}, [], "Choose at least one file"),
        ({"max_files": 1}, [("a", b"1"), ("b", b"2")], "Upload limit exceeded"),
        ({"max_file_bytes": 2}, [("a", b"123")], "Upload limit exceeded"),
        ({"max_total_bytes": 3}, [("a", b"12"), ("b", b"34")], "Upload limit exceeded"),
    ],
)
def test_upload_limits_precede_builder(config, uploads, message):
    from app_factory import IntakeFiles

    async def build(*args):
        pytest.fail("invalid uploads must not reach builder")

    client, calls, _ = make_host(files=IntakeFiles(**config), builder=build)
    data = {**Inputs(client.get("/intake").text).values, "title": "Example"}
    response = client.post(
        "/intake", data=data, files=[("files", (name, body)) for name, body in uploads]
    )
    assert response.status_code in (413, 422)
    assert message in response.text and 'id="intake-files-error"' in response.text
    assert "Select files again" in response.text
    assert not calls


def test_upload_handles_close_on_domain_failure(monkeypatch):
    from starlette.datastructures import UploadFile
    from app_factory import IntakeError, IntakeFiles

    closed = []
    original = UploadFile.close

    async def close(self):
        await original(self)
        closed.append(self.file.closed)

    monkeypatch.setattr(UploadFile, "close", close)

    async def build(*args):
        raise IntakeError({"files": "Not accepted"})

    client, calls, _ = make_host(files=IntakeFiles(), builder=build)
    data = {**Inputs(client.get("/intake").text).values, "title": "Example"}
    response = client.post("/intake", data=data, files={"files": ("a.txt", b"abc")})
    assert response.status_code == 422
    assert closed == [True] and not calls


def test_empty_browser_file_part_is_not_an_upload():
    from app_factory import IntakeFiles

    client, calls, _ = make_host(files=IntakeFiles())
    data = {**Inputs(client.get("/intake").text).values, "title": "Example"}
    response = client.post(
        "/intake", data=data, files={"files": ("", b"")}, headers={"HX-Request": "true"}
    )
    assert response.status_code == 200 and "run-1" in response.text
    assert calls[0][1].input["files"] == []


def test_request_limit_applies_without_content_length():
    client, calls, _ = make_host()
    response = client.post(
        "/intake",
        content=iter([b"x" * (1024 * 1024)] * 18),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert (
        response.status_code == 413 and "Request size limit exceeded" in response.text
    )
    assert not calls


@pytest.mark.parametrize(
    "factory,kwargs",
    [
        ("IntakeField", {"name": "bad name", "label": "Bad"}),
        ("IntakeField", {"name": "csrf_token", "label": "Bad"}),
        ("IntakeField", {"name": "ok", "label": "Bad", "kind": "unknown"}),
        ("IntakeField", {"name": "ok", "label": "Bad", "max_length": 0}),
        ("IntakeFiles", {"max_files": 0}),
        ("IntakeFiles", {"max_file_bytes": 0}),
        ("IntakeFiles", {"max_total_bytes": 0}),
        ("IntakeSpec", {"id": "bad#target"}),
        ("IntakeSpec", {"max_request_bytes": 0}),
    ],
)
def test_invalid_specs_fail_at_configuration(factory, kwargs):
    import app_factory

    with pytest.raises(ValueError):
        getattr(app_factory, factory)(**kwargs)


def test_duplicate_field_names_are_rejected():
    from app_factory import IntakeField, IntakeFiles, IntakeSpec

    field = IntakeField(name="title", label="Title")
    with pytest.raises(ValueError):
        IntakeSpec(fields=(field, field))
    with pytest.raises(ValueError):
        IntakeSpec(fields=(field,), files=IntakeFiles(name="title"))


def test_shared_upload_controller_allows_optional_empty_input():
    source = (
        configure_jinja_env(Environment())
        .get_template("app_factory/file_upload_boot.html")
        .render()
    )
    assert "if (!files.length && input.required)" in source
    assert "submit.disabled = input.required && files.length === 0" in source
    assert (
        "submit.disabled = input.required && !(input.files && input.files.length)"
        in source
    )


def test_browser_htmx_swaps_errors_then_receipt_with_optional_upload():
    playwright = pytest.importorskip("playwright.sync_api")
    from pathlib import Path
    from app_factory import IntakeError, IntakeFiles

    async def build(request, scope, submission):
        if submission.fields["title"] == "Bad":
            raise IntakeError({"title": "Choose another title"})
        return RunIntent(kind="example", input=submission.fields)

    client, calls, _ = make_host(files=IntakeFiles(), builder=build)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def respond(route):
            req = route.request
            response = client.request(
                req.method,
                req.url,
                content=req.post_data_buffer,
                headers=req.headers,
                follow_redirects=False,
            )
            body = response.content
            if req.method == "GET":
                body += (
                    configure_jinja_env(Environment())
                    .get_template("app_factory/file_upload_boot.html")
                    .render()
                    .encode()
                )
            route.fulfill(
                status=response.status_code, headers=dict(response.headers), body=body
            )

        page.route("http://testserver/**", respond)
        try:
            page.goto("http://testserver/intake")
            assets = Path(__file__).parents[1] / "app_factory/assets"
            page.add_script_tag(path=str(assets / "htmx.min.js"))
            page.add_script_tag(path=str(assets / "alpine.min.js"))
            page.locator('[name="title"]').fill("Bad")
            page.get_by_role("button", name="Start", exact=True).click()
            page.locator("#intake-title-error").wait_for()
            assert not calls
            page.locator('[name="title"]').fill("Good")
            page.get_by_role("button", name="Start", exact=True).click()
            page.locator("#intake-status").wait_for()
            assert page.locator("#intake-status").inner_text() == "pending"
            assert len(calls) == 1 and not errors
        finally:
            browser.close()
