"""Reference hosts only: no in-memory run backend ships in app_factory."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient


def test_run_detail_page_and_htmx_fragment():
    import app_factory
    from jinja2 import Environment, select_autoescape

    factory = getattr(app_factory, "create_run_view_router", None)
    assert callable(factory), "Missing opt-in server-rendered run views"
    environment = Environment(autoescape=select_autoescape())
    app = FastAPI()
    app_factory.install_platform(app, environments=[environment])
    calls = []

    class Port:
        async def get_run(self, scope, run_id):
            calls.append((scope, run_id))
            return app_factory.Run(
                id=run_id, status="pending", created_at=datetime.now(timezone.utc)
            )

    async def authorize(request, action, *, run_id=None, intent=None):
        assert action == "read"
        return "alice"

    app.include_router(factory(lambda: Port(), authorize, environment=environment))
    with TestClient(app) as client:
        full = client.get("/runs/one")
        fragment = client.get("/runs/one", headers={"HX-Request": "true"})
    assert full.status_code == fragment.status_code == 200
    assert "<html" in full.text and 'id="sidebar"' in full.text
    assert "<html" not in fragment.text and "<script" not in fragment.text
    assert 'id="run-detail"' in fragment.text
    assert 'data-run-status="pending"' in fragment.text
    assert 'hx-trigger="every 2s"' in fragment.text
    assert 'hx-target="#run-detail"' in fragment.text
    assert 'hx-swap="outerHTML"' in fragment.text
    assert full.headers["cache-control"] == "no-store"
    assert calls == [("alice", "one")] * 2


@pytest.fixture
def run_view_host():
    from app_factory import (
        Run,
        RunPage,
        RunError,
        create_run_view_router,
        install_platform,
    )
    from jinja2 import Environment, select_autoescape

    class Port:
        run = Run(id="one", status="pending", created_at=datetime.now(timezone.utc))
        error = None
        calls = []

        async def get_run(self, scope, run_id):
            self.calls.append((scope, run_id))
            if self.error:
                raise self.error
            return self.run

        async def list_runs(self, scope, *, cursor, limit):
            self.calls.append((scope, cursor, limit))
            if self.error:
                raise self.error
            return RunPage(items=[])

    port = Port()
    environment = Environment(autoescape=select_autoescape())
    app = FastAPI()
    install_platform(app, environments=[environment])

    async def authorize(request, action, *, run_id=None, intent=None):
        if request.headers.get("X-Deny"):
            raise RunError("unauthorized", "Sign in")
        return request.headers.get("X-Owner", "alice")

    app.include_router(
        create_run_view_router(lambda: port, authorize, environment=environment)
    )
    with TestClient(app) as client:
        yield client, port


@pytest.mark.parametrize(
    "status",
    ["pending", "running", "waiting", "succeeded", "failed", "cancelled"],
)
def test_presentation_status_polling_and_waiting(run_view_host, status):
    from app_factory import Run

    client, port = run_view_host
    port.run = Run(
        id="one",
        status=status,
        created_at=datetime.now(timezone.utc),
        waiting_reason="Awaiting <approval>",
        next_observation="Check tomorrow",
        retry_after=7,
    )
    response = client.get("/runs/one", headers={"HX-Request": "true"})
    assert response.status_code == 200
    terminal = status in {"succeeded", "failed", "cancelled"}
    assert ('hx-trigger="every 7s"' in response.text) == (not terminal)
    assert (response.headers.get("Retry-After") == "7") == (not terminal)
    if status == "waiting":
        assert "Awaiting &lt;approval&gt;" in response.text
        assert "Check tomorrow" in response.text
    else:
        assert "Check tomorrow" not in response.text


def test_run_history_cursor_preserves_filters_and_scope(run_view_host):
    from html import unescape
    import re
    from urllib.parse import parse_qs, urlsplit
    from app_factory import RunPage

    client, port = run_view_host

    async def history(scope, *, cursor, limit):
        port.calls.append((scope, cursor, limit))
        return RunPage(items=[port.run], next_cursor="alice:next &/?")

    port.list_runs = history
    response = client.get(
        "/runs?limit=1&tag=a&tag=b&status=waiting", headers={"HX-Request": "true"}
    )
    assert response.status_code == 200
    assert "<html" not in response.text
    assert 'id="run-history"' in response.text
    assert "data-run-history-row" in response.text
    url = unescape(re.search(r'href="([^"]+)"[^>]*rel="next"', response.text).group(1))
    assert parse_qs(urlsplit(url).query) == {
        "limit": ["1"],
        "tag": ["a", "b"],
        "status": ["waiting"],
        "cursor": ["alice:next &/?"],
    }
    client.get(url, headers={"X-Owner": "bob"})
    assert port.calls[-1] == ("bob", "alice:next &/?", 1)
    before = len(port.calls)
    denied = client.get(url, headers={"X-Deny": "yes", "HX-Request": "true"})
    assert 'data-run-state="unauthorized"' in denied.text
    assert len(port.calls) == before


def test_run_history_empty_and_invalid_query(run_view_host):
    client, port = run_view_host
    assert 'data-run-state="empty"' in client.get("/runs").text
    for query in ["limit=0", "limit=101", "cursor="]:
        response = client.get("/runs?" + query)
        assert response.status_code == 422
        assert 'data-run-state="invalid-request"' in response.text


@pytest.mark.parametrize(
    "code,status,state",
    [
        ("unauthorized", 401, "unauthorized"),
        ("forbidden", 403, "unauthorized"),
        ("not_found", 404, "not-found"),
        ("unavailable", 503, "transient-error"),
        ("stale_version", 409, "stale-version"),
    ],
)
def test_run_view_errors_swap_and_stop_or_back_off(run_view_host, code, status, state):
    from app_factory import RunError

    client, port = run_view_host
    port.error = RunError(
        code, "Safe <message>", retry_after=9 if code == "unavailable" else None
    )
    for path, target in [("/runs/one", "run-detail"), ("/runs", "run-history")]:
        native = client.get(path)
        fragment = client.get(path, headers={"HX-Request": "true"})
        assert native.status_code == status
        assert (
            fragment.status_code == 200
        )  # deliberate HTML error state, HTMX swaps by default
        assert "<html" not in fragment.text
        assert f'id="{target}"' in fragment.text
        assert f'data-run-state="{state}"' in fragment.text
        assert "Safe &lt;message&gt;" in fragment.text
        assert ('hx-trigger="every 9s"' in fragment.text) == (code == "unavailable")
        assert fragment.headers["cache-control"] == "no-store"
        assert "HX-History-Restore-Request" in fragment.headers["vary"]


def test_run_history_restore_returns_fresh_full_shell(run_view_host):
    client, port = run_view_host
    response = client.get(
        "/runs/one",
        headers={"HX-Request": "true", "HX-History-Restore-Request": "true"},
    )
    assert "<html" in response.text and 'id="sidebar"' in response.text
    assert 'hx-history="false"' not in response.text
    assert port.calls == [("alice", "one")]


def test_run_view_dependency_errors_are_html_and_retry_metadata_reaches_json():
    from app_factory import (
        RunError,
        create_run_router,
        create_run_view_router,
        install_platform,
    )
    from jinja2 import Environment, select_autoescape

    def dependency():
        raise RunError("unavailable", "Try later", retry_after=13)

    async def authorize(*args, **kwargs):
        return "alice"

    app = FastAPI()
    env = Environment(autoescape=select_autoescape())
    install_platform(app, environments=[env])
    app.include_router(create_run_view_router(dependency, authorize, environment=env))
    app.include_router(create_run_router(dependency, authorize, prefix="/api/runs"))
    with TestClient(app) as client:
        html = client.get("/runs", headers={"HX-Request": "true"})
        assert 'data-run-state="transient-error"' in html.text
        assert html.headers["Retry-After"] == "13"
        api = client.get("/api/runs")
        assert api.status_code == 503
        assert api.headers["Retry-After"] == "13"
        assert api.json()["retry_after"] == 13


@pytest.mark.parametrize("delay", [0, -1, 1.5, float("inf")])
def test_run_retry_after_rejects_invalid_intervals(delay):
    from app_factory import Run, RunError
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Run(
            id="one",
            status="running",
            created_at=datetime.now(timezone.utc),
            retry_after=delay,
        )
    with pytest.raises(ValidationError):
        RunError("unavailable", "Retry later", retry_after=delay)


def test_run_history_filters_are_host_owned_and_applied_before_paging():
    from app_factory import (
        Run,
        RunPage,
        RunError,
        create_run_view_router,
        install_platform,
    )
    from jinja2 import Environment, select_autoescape

    records = [
        ("alice", "red", "a"),
        ("alice", "blue", "b"),
        ("alice", "red", "c"),
        ("bob", "red", "secret"),
    ]

    def dependency(request: Request):
        tag = request.query_params.get("tag")

        class Port:
            async def list_runs(self, scope, *, cursor, limit):
                filtered = [
                    id
                    for owner, color, id in records
                    if owner == scope and color == tag
                ]
                if cursor and cursor not in filtered:
                    raise RunError("invalid_request", "Invalid cursor")
                start = filtered.index(cursor) + 1 if cursor else 0
                ids = filtered[start : start + limit]
                return RunPage(
                    items=[
                        Run(
                            id=id,
                            status="succeeded",
                            created_at=datetime.now(timezone.utc),
                        )
                        for id in ids
                    ],
                    next_cursor=ids[-1] if start + limit < len(filtered) else None,
                )

        return Port()

    async def authorize(request, action, **kwargs):
        return request.headers.get("X-Owner", "alice")

    app = FastAPI()
    env = Environment(autoescape=select_autoescape())
    install_platform(app, environments=[env])
    app.include_router(
        create_run_view_router(
            dependency, authorize, environment=env, prefix="/portal/runs"
        )
    )
    with TestClient(app) as client:
        first = client.get("/portal/runs?tag=red&limit=1")
        assert 'data-run-id="a"' in first.text
        assert 'href="/portal/runs/a"' in first.text
        assert 'data-run-id="b"' not in first.text
        last = client.get("/portal/runs?tag=red&limit=1&cursor=a")
        assert 'data-run-id="c"' in last.text and 'rel="next"' not in last.text
        foreign = client.get(
            "/portal/runs?tag=red&limit=1&cursor=a", headers={"X-Owner": "bob"}
        )
        assert foreign.status_code == 422
        assert "secret" not in foreign.text


def test_create_retry_uses_host_idempotency_and_authorization():
    from app_factory import Run, RunIntent, create_run_router

    class MemoryPort:
        def __init__(self):
            self.runs = {}
            self.calls = []

        async def create_intent(self, scope, intent, *, idempotency_key):
            self.calls.append((scope, intent, idempotency_key))
            key = (scope, idempotency_key)
            if key not in self.runs:
                self.runs[key] = Run(
                    id=str(len(self.runs) + 1),
                    status="pending",
                    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                )
            return self.runs[key]

    port = MemoryPort()
    authorized = []

    async def authorize(request: Request, action, *, run_id=None, intent=None):
        authorized.append((action, run_id, intent))
        return "user-1"

    app = FastAPI()
    app.include_router(create_run_router(lambda: port, authorize))
    with TestClient(app) as client:
        response = client.post(
            "/runs",
            json={"kind": "example", "input": {"value": 3}},
            headers={"Idempotency-Key": "retry-1"},
        )
        retry = client.post(
            "/runs",
            json={"kind": "example", "input": {"value": 3}},
            headers={"Idempotency-Key": "retry-1"},
        )
    assert response.status_code == retry.status_code == 202
    assert response.json() == retry.json()
    assert response.json()["version"] == "v1"
    assert len(port.runs) == 1
    assert (
        port.calls
        == [("user-1", RunIntent(kind="example", input={"value": 3}), "retry-1")] * 2
    )
    assert (
        authorized
        == [("create", None, RunIntent(kind="example", input={"value": 3}))] * 2
    )


@pytest.fixture(params=["memory", "projection"])
def reference_host(request):
    from app_factory import (
        Run,
        RunArtifact,
        RunArtifacts,
        RunError,
        RunIntent,
        RunPage,
        create_run_router,
    )

    class MemoryPort:
        def __init__(self):
            self.runs = {}
            self.keys = {}

        async def create_intent(self, scope, intent, *, idempotency_key):
            key = (scope, idempotency_key)
            if key in self.keys:
                previous, run_id = self.keys[key]
                if previous != intent:
                    raise RunError("conflict", "Key reused with different intent")
                return self.runs[scope, run_id]
            run = Run(
                id=str(len(self.runs) + 1),
                status="pending",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            self.runs[scope, run.id] = run
            self.keys[key] = (intent, run.id)
            return run

        async def get_run(self, scope, run_id):
            if (scope, run_id) not in self.runs:
                raise RunError("not_found", "Run not found")
            return self.runs[scope, run_id]

        async def list_runs(self, scope, *, cursor, limit):
            runs = [run for (owner, _), run in self.runs.items() if owner == scope]
            start = 0
            if cursor:
                prefix = f"opaque:{scope}:"
                if not cursor.startswith(prefix) or not cursor[len(prefix) :].isdigit():
                    raise RunError("invalid_request", "Invalid cursor")
                start = int(cursor[len(prefix) :])
                if not 0 < start < len(runs):
                    raise RunError("invalid_request", "Invalid cursor")
            end = start + limit
            return RunPage(
                items=runs[start:end],
                next_cursor=f"opaque:{scope}:{end}" if end < len(runs) else None,
            )

        async def request_cancel(self, scope, run_id):
            run = await self.get_run(scope, run_id)
            self.runs[scope, run_id] = run.model_copy(update={"status": "cancelled"})
            return self.runs[scope, run_id]

        async def list_artifacts(self, scope, run_id):
            await self.get_run(scope, run_id)
            return RunArtifacts(
                items=[
                    RunArtifact(
                        id="output",
                        label="Output",
                        href=f"/files/{run_id}",
                        media_type="text/plain",
                    )
                ]
            )

    class ProjectionPort:
        """Different native record shape/status vocabulary, projected at boundary."""

        def __init__(self):
            self.jobs = []

        def dto(self, job):
            return Run(
                id=job["ref"],
                status={0: "pending", 9: "cancelled"}[job["phase"]],
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

        def find(self, scope, run_id):
            for job in self.jobs:
                if job["owner"] == scope and job["ref"] == run_id:
                    return job
            raise RunError("not_found", "Run not found")

        async def create_intent(self, scope, intent, *, idempotency_key):
            for job in self.jobs:
                if (job["owner"], job["token"]) == (scope, idempotency_key):
                    if job["payload"] != intent.model_dump():
                        raise RunError("conflict", "Key reused with different intent")
                    return self.dto(job)
            job = dict(
                ref=f"job-{len(self.jobs)}",
                owner=scope,
                token=idempotency_key,
                payload=intent.model_dump(),
                phase=0,
            )
            self.jobs.append(job)
            return self.dto(job)

        async def get_run(self, scope, run_id):
            return self.dto(self.find(scope, run_id))

        async def list_runs(self, scope, *, cursor, limit):
            jobs = [job for job in self.jobs if job["owner"] == scope]
            start = 0
            if cursor:
                start = next(
                    (i + 1 for i, job in enumerate(jobs) if job["ref"] == cursor), 0
                )
                if start == 0:
                    raise RunError("invalid_request", "Invalid cursor")
            page = jobs[start : start + limit]
            return RunPage(
                items=[self.dto(job) for job in page],
                next_cursor=page[-1]["ref"] if start + limit < len(jobs) else None,
            )

        async def request_cancel(self, scope, run_id):
            job = self.find(scope, run_id)
            job["phase"] = 9
            return self.dto(job)

        async def list_artifacts(self, scope, run_id):
            self.find(scope, run_id)
            return RunArtifacts(
                items=[
                    RunArtifact(
                        id="output",
                        label="Output",
                        href=f"/files/{run_id}",
                        media_type="text/plain",
                    )
                ]
            )

    port = MemoryPort() if request.param == "memory" else ProjectionPort()
    calls = []
    policy_calls = []

    class ObservedPort:
        def __getattr__(self, name):
            async def invoke(*args, **kwargs):
                calls.append(name)
                return await getattr(port, name)(*args, **kwargs)

            return invoke

    async def authorize(request: Request, action, *, run_id=None, intent=None):
        policy_calls.append((action, run_id, intent))
        if request.headers.get("X-Deny"):
            raise RunError("forbidden", "Access denied")
        return request.headers.get("X-Owner", "alice")

    def get_backend():
        return ObservedPort()

    async def dependency(backend=Depends(get_backend)):
        return backend

    app = FastAPI()
    app.include_router(create_run_router(dependency, authorize, prefix="/api/runs"))
    with TestClient(app) as client:
        yield client, calls, policy_calls, RunIntent


def test_same_router_supports_two_backends(reference_host):
    client, calls, policy, _ = reference_host

    def create(key, **headers):
        return client.post(
            "/api/runs",
            json={"kind": "example"},
            headers={"Idempotency-Key": key, **headers},
        )

    first = create("one")
    assert first.status_code == 202
    assert create("one").json() == first.json()
    second = create("two").json()
    other = create("one", **{"X-Owner": "bob"}).json()
    run_id = first.json()["id"]
    assert other["id"] != run_id
    conflict = client.post(
        "/api/runs", json={"kind": "different"}, headers={"Idempotency-Key": "one"}
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "conflict"
    page = client.get("/api/runs", params={"limit": 1}).json()
    assert page["items"] == [first.json()]
    assert page["version"] == "v1"
    last = client.get(
        "/api/runs", params={"limit": 1, "cursor": page["next_cursor"]}
    ).json()
    assert last["items"] == [second]
    assert last["next_cursor"] is None
    assert client.get(f"/api/runs/{run_id}").json() == first.json()
    denied = client.get(f"/api/runs/{run_id}", headers={"X-Owner": "bob"})
    assert denied.status_code == 404
    artifacts = client.get(f"/api/runs/{run_id}/artifacts").json()
    assert artifacts["version"] == "v1"
    assert artifacts["items"][0]["href"] == f"/files/{run_id}"
    cancelled = client.post(f"/api/runs/{run_id}/cancel")
    assert cancelled.status_code == 202
    assert cancelled.json()["status"] == "cancelled"
    assert [p[0] for p in policy] == [
        "create",
        "create",
        "create",
        "create",
        "create",
        "read",
        "read",
        "read",
        "read",
        "artifact",
        "cancel",
    ]
    assert set(calls) == {
        "create_intent",
        "list_runs",
        "get_run",
        "list_artifacts",
        "request_cancel",
    }


@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        (
            "post",
            "",
            {"json": {"kind": "example"}, "headers": {"Idempotency-Key": "key"}},
        ),
        ("get", "", {}),
        ("get", "/secret", {}),
        ("post", "/secret/cancel", {}),
        ("get", "/secret/artifacts", {}),
    ],
)
def test_denial_never_calls_port(reference_host, method, path, kwargs):
    client, calls, policy, _ = reference_host
    kwargs["headers"] = {**kwargs.get("headers", {}), "X-Deny": "yes"}
    response = getattr(client, method)("/api/runs" + path, **kwargs)
    assert response.status_code == 403
    assert response.json() == {
        "version": "v1",
        "code": "forbidden",
        "message": "Access denied",
    }
    assert not calls
    assert len(policy) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"json": {"kind": "example"}},
        {"json": {"kind": "example"}, "headers": {"Idempotency-Key": "   "}},
        {
            "json": {"kind": "example", "version": "v2"},
            "headers": {"Idempotency-Key": "key"},
        },
        {
            "json": {"kind": "example", "unknown": True},
            "headers": {"Idempotency-Key": "key"},
        },
        {"json": {"kind": ""}, "headers": {"Idempotency-Key": "key"}},
    ],
)
def test_invalid_create_has_versioned_error(reference_host, kwargs):
    client, calls, policy, _ = reference_host
    response = client.post("/api/runs", **kwargs)
    assert response.status_code == 422
    assert response.json() == {
        "version": "v1",
        "code": "invalid_request",
        "message": "Invalid run request",
    }
    assert not calls and not policy


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"cursor": ""}])
def test_invalid_pagination_has_versioned_error(reference_host, params):
    client, calls, _, _ = reference_host
    response = client.get("/api/runs", params=params)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
    assert not calls


def test_v1_schema_is_closed_and_documented(reference_host):
    from app_factory import Run, RunErrorResponse
    from pydantic import ValidationError

    client, _, _, _ = reference_host
    schema = client.get("/openapi.json").json()
    models = schema["components"]["schemas"]
    assert models["Run"]["properties"]["status"]["enum"] == [
        "pending",
        "running",
        "waiting",
        "succeeded",
        "failed",
        "cancelled",
    ]
    for name in [
        "Run",
        "RunIntent",
        "RunPage",
        "RunArtifacts",
        "RunArtifact",
        "RunErrorResponse",
    ]:
        assert models[name]["properties"]["version"]["const"] == "v1"
        assert models[name]["additionalProperties"] is False
    for path in schema["paths"].values():
        for operation in path.values():
            assert operation["responses"]["422"]["content"]["application/json"][
                "schema"
            ] == {
                "$ref": "#/components/schemas/RunErrorResponse",
            }
    with pytest.raises(ValidationError):
        Run(id="one", status="engine_checkpoint", created_at=datetime.now(timezone.utc))
    with pytest.raises(ValidationError):
        RunErrorResponse(code="domain_failure", message="not public")


def test_concurrent_create_retries_have_one_history_item(reference_host):
    client, _, _, _ = reference_host

    def create(_):
        response = client.post(
            "/api/runs",
            json={"kind": "example"},
            headers={"Idempotency-Key": "concurrent-retry"},
        )
        assert response.status_code == 202
        return response.json()["id"]

    with ThreadPoolExecutor(max_workers=4) as workers:
        ids = list(workers.map(create, range(8)))
    assert len(set(ids)) == 1
    assert len(client.get("/api/runs").json()["items"]) == 1


def test_cursors_cannot_cross_scopes(reference_host):
    client, _, _, _ = reference_host
    for key in ["one", "two"]:
        client.post(
            "/api/runs", json={"kind": "example"}, headers={"Idempotency-Key": key}
        )
    cursor = client.get("/api/runs", params={"limit": 1}).json()["next_cursor"]
    for value in [cursor, "unknown"]:
        response = client.get(
            "/api/runs", params={"cursor": value}, headers={"X-Owner": "bob"}
        )
        assert response.status_code == 422
        assert response.json()["code"] == "invalid_request"


def test_run_results_present_local_external_and_metadata_only():
    from app_factory import (
        Run,
        RunArtifact,
        RunResult,
        create_run_view_router,
        install_platform,
    )
    from jinja2 import Environment, select_autoescape

    class Port:
        async def get_run(self, scope, run_id):
            return Run(
                id=run_id,
                status="succeeded",
                created_at=datetime.now(timezone.utc),
            )

        async def get_result(self, scope, run_id):
            return RunResult(
                run_id=run_id,
                values={"score": 3, "note": "ok <done>"},
                links=[
                    RunArtifact(
                        id="pr",
                        label="Pull request",
                        media_type="text/html",
                        href="https://example.test/pr/1",
                    )
                ],
                artifacts=[
                    RunArtifact(
                        id="report",
                        label="Report",
                        media_type="application/pdf",
                        size=12,
                        digest="sha256:aaaaaaaa",
                        disposition="attachment",
                        filename="report.pdf",
                    ),
                    RunArtifact(
                        id="summary",
                        label="Summary",
                        media_type="application/json",
                    ),
                ],
            )

    async def authorize(request, action, *, run_id=None, intent=None):
        return "alice"

    environment = Environment(autoescape=select_autoescape())
    app = FastAPI()
    install_platform(app, environments=[environment])
    app.include_router(
        create_run_view_router(lambda: Port(), authorize, environment=environment)
    )
    with TestClient(app) as client:
        full = client.get("/runs/one")
        fragment = client.get("/runs/one", headers={"HX-Request": "true"})
    assert full.status_code == fragment.status_code == 200
    assert "<html" in full.text and 'id="sidebar"' in full.text
    assert "<html" not in fragment.text
    assert 'id="run-results"' in fragment.text
    assert "score" in fragment.text and "3" in fragment.text
    assert "ok &lt;done&gt;" in fragment.text
    assert 'href="https://example.test/pr/1"' in fragment.text
    assert "Pull request" in fragment.text
    assert 'href="/runs/one/artifacts/report"' in fragment.text
    assert "Report" in fragment.text
    assert "report.pdf" in fragment.text
    assert "sha256:aaaaaaaa" in fragment.text
    assert 'href="/runs/one/artifacts/summary"' not in fragment.text
    assert "Summary" in fragment.text
    assert 'data-artifact-kind="download"' in fragment.text
    assert 'data-artifact-kind="external"' in fragment.text
    assert 'data-artifact-kind="metadata"' in fragment.text


@pytest.mark.parametrize("status", ["running", "failed", "cancelled", "waiting"])
def test_run_results_stay_hidden_until_terminal_success(status):
    from app_factory import Run, create_run_view_router, install_platform
    from jinja2 import Environment, select_autoescape

    class Port:
        called = False

        async def get_run(self, scope, run_id):
            return Run(id=run_id, status=status, created_at=datetime.now(timezone.utc))

        async def get_result(self, scope, run_id):
            self.called = True
            raise AssertionError("results are not ready")

    port = Port()

    async def authorize(request, action, *, run_id=None, intent=None):
        return "alice"

    environment = Environment(autoescape=select_autoescape())
    app = FastAPI()
    install_platform(app, environments=[environment])
    app.include_router(
        create_run_view_router(lambda: port, authorize, environment=environment)
    )
    with TestClient(app) as client:
        response = client.get("/runs/one", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert 'id="run-results"' not in response.text
    assert port.called is False


def test_artifact_download_reauthorizes_and_sets_safe_headers():
    from app_factory import (
        Run,
        RunArtifact,
        RunArtifactStream,
        create_run_view_router,
        install_platform,
    )
    from jinja2 import Environment, select_autoescape

    payload = b"%PDF-report"
    calls = []

    class Port:
        async def get_run(self, scope, run_id):
            return Run(
                id=run_id, status="succeeded", created_at=datetime.now(timezone.utc)
            )

        async def open_artifact(self, scope, run_id, artifact_id):
            calls.append((scope, run_id, artifact_id))
            return RunArtifactStream(
                artifact=RunArtifact(
                    id=artifact_id,
                    label="Report",
                    media_type="application/pdf",
                    size=len(payload),
                    digest="sha256:deadbeef",
                    disposition="attachment",
                    filename="../evil\r\nX-Injected: yes.pdf",
                ),
                body=iter([payload]),
                digest="sha256:deadbeef",
            )

    async def authorize(request, action, *, run_id=None, intent=None):
        calls.append((action, run_id))
        return "alice"

    environment = Environment(autoescape=select_autoescape())
    app = FastAPI()
    install_platform(app, environments=[environment])
    app.include_router(
        create_run_view_router(lambda: Port(), authorize, environment=environment)
    )
    with TestClient(app) as client:
        response = client.get("/runs/one/artifacts/report")
    assert response.status_code == 200
    assert response.content == payload
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["x-content-type-options"] == "nosniff"
    disposition = response.headers["content-disposition"]
    assert "attachment" in disposition
    assert "../" not in disposition
    assert "\r" not in disposition and "\n" not in disposition
    assert "X-Injected" not in disposition
    assert "evil" in disposition
    assert calls[0] == ("artifact", "one")
    assert ("alice", "one", "report") in calls


def test_artifact_download_denies_without_authority():
    from app_factory import RunError, create_run_view_router, install_platform
    from jinja2 import Environment, select_autoescape

    called = False

    class Port:
        async def open_artifact(self, scope, run_id, artifact_id):
            nonlocal called
            called = True
            raise AssertionError("port must not stream unauthorized artifacts")

    async def authorize(request, action, *, run_id=None, intent=None):
        raise RunError("forbidden", "Access denied")

    environment = Environment(autoescape=select_autoescape())
    app = FastAPI()
    install_platform(app, environments=[environment])
    app.include_router(
        create_run_view_router(lambda: Port(), authorize, environment=environment)
    )
    with TestClient(app) as client:
        native = client.get("/runs/one/artifacts/secret")
        fragment = client.get(
            "/runs/one/artifacts/secret", headers={"HX-Request": "true"}
        )
    assert native.status_code == 403
    assert called is False
    assert 'data-run-state="unauthorized"' in native.text
    assert "<html" not in fragment.text
    assert 'data-run-state="unauthorized"' in fragment.text


def test_artifact_states_are_explicit_and_visible():
    from app_factory import (
        RunArtifact,
        RunArtifactStream,
        RunError,
        create_run_view_router,
        install_platform,
    )
    from jinja2 import Environment, select_autoescape

    class Port:
        error = None
        stream = None

        async def open_artifact(self, scope, run_id, artifact_id):
            if self.error:
                raise self.error
            return self.stream

    port = Port()

    async def authorize(request, action, *, run_id=None, intent=None):
        return "alice"

    environment = Environment(autoescape=select_autoescape())
    app = FastAPI()
    install_platform(app, environments=[environment])
    app.include_router(
        create_run_view_router(lambda: port, authorize, environment=environment)
    )
    cases = [
        (RunError("not_found", "Artifact missing"), 404, "not-found"),
        (RunError("unavailable", "Artifact pending"), 503, "transient-error"),
        (RunError("conflict", "Artifact expired"), 409, "stale-version"),
    ]
    with TestClient(app) as client:
        for error, status, state in cases:
            port.error = error
            native = client.get("/runs/one/artifacts/report")
            fragment = client.get(
                "/runs/one/artifacts/report", headers={"HX-Request": "true"}
            )
            assert native.status_code == status
            assert f'data-run-state="{state}"' in native.text
            assert "<html" not in fragment.text
            assert f'data-run-state="{state}"' in fragment.text
            assert (
                error.response.message in fragment.text or "Artifact" in fragment.text
            )

        port.error = None
        port.stream = RunArtifactStream(
            artifact=RunArtifact(
                id="report",
                label="Report",
                media_type="text/plain",
                digest="sha256:expected",
                filename="report.txt",
            ),
            body=iter([b"hello"]),
            digest="sha256:other",
        )
        mismatch = client.get("/runs/one/artifacts/report")
        fragment = client.get(
            "/runs/one/artifacts/report", headers={"HX-Request": "true"}
        )
    assert mismatch.status_code == 409
    assert "digest" in mismatch.text.lower()
    assert "<html" not in fragment.text
    assert 'data-run-state="stale-version"' in fragment.text
    assert "digest" in fragment.text.lower()


def test_json_artifact_download_reauthorizes_and_rejects_mismatch():
    from app_factory import (
        RunArtifact,
        RunArtifactStream,
        RunError,
        create_run_router,
    )

    payload = b"report-bytes"
    calls = []

    class Port:
        artifact_digest = "sha256:deadbeef"
        stream_digest = "sha256:deadbeef"

        async def open_artifact(self, scope, run_id, artifact_id):
            calls.append((scope, run_id, artifact_id))
            return RunArtifactStream(
                artifact=RunArtifact(
                    id=artifact_id,
                    label="Report",
                    media_type="application/pdf",
                    digest=self.artifact_digest,
                    filename="../evil\r\nX-Injected: yes.pdf",
                ),
                body=iter([payload]),
                digest=self.stream_digest,
            )

    port = Port()

    async def authorize(request, action, *, run_id=None, intent=None):
        calls.append((action, run_id))
        if request.headers.get("X-Deny"):
            raise RunError("forbidden", "Access denied")
        return "alice"

    app = FastAPI()
    app.include_router(create_run_router(lambda: port, authorize, prefix="/api/runs"))
    with TestClient(app) as client:
        denied = client.get("/api/runs/one/artifacts/report", headers={"X-Deny": "yes"})
        assert denied.status_code == 403
        assert denied.json()["code"] == "forbidden"
        assert calls == [("artifact", "one")]
        ok = client.get("/api/runs/one/artifacts/report")
        port.stream_digest = "sha256:otherxxxx"
        mismatch = client.get("/api/runs/one/artifacts/report")
    assert ok.status_code == 200
    assert ok.content == payload
    assert ok.headers["x-content-type-options"] == "nosniff"
    assert "../" not in ok.headers["content-disposition"]
    assert "X-Injected" not in ok.headers["content-disposition"]
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "conflict"
    assert "digest" in mismatch.json()["message"].lower()


@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(document.domain)",
        "JAVASCRIPT:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "java\nscript:alert(1)",
        "\x00javascript:alert(1)",
        "https://example.test/ok\r\nX-Injected: yes",
    ],
)
def test_result_href_rejects_non_http_schemes(href):
    from app_factory import (
        Run,
        RunArtifact,
        RunResult,
        create_run_view_router,
        install_platform,
    )
    from jinja2 import Environment, select_autoescape

    artifact = RunArtifact(
        id="xss",
        label="Unsafe",
        media_type="text/html",
        href=href,
    )
    assert artifact.href is None or artifact.href.startswith(("http://", "https://"))
    assert artifact.href is None

    class Port:
        async def get_run(self, scope, run_id):
            return Run(
                id=run_id, status="succeeded", created_at=datetime.now(timezone.utc)
            )

        async def get_result(self, scope, run_id):
            return RunResult(run_id=run_id, links=[artifact])

    async def authorize(request, action, *, run_id=None, intent=None):
        return "alice"

    environment = Environment(autoescape=select_autoescape())
    app = FastAPI()
    install_platform(app, environments=[environment])
    app.include_router(
        create_run_view_router(lambda: Port(), authorize, environment=environment)
    )
    with TestClient(app) as client:
        fragment = client.get("/runs/one", headers={"HX-Request": "true"})
    assert fragment.status_code == 200
    assert "javascript:" not in fragment.text.lower()
    assert "data:text/html" not in fragment.text.lower()
    assert 'href="javascript' not in fragment.text.lower()
    assert "Unsafe" in fragment.text


def test_artifact_filename_fallback_strips_header_injection():
    from app_factory import (
        RunArtifact,
        RunArtifactStream,
        create_run_view_router,
        install_platform,
    )
    from jinja2 import Environment, select_autoescape

    payload = b"bytes"

    class Port:
        async def open_artifact(self, scope, run_id, artifact_id):
            return RunArtifactStream(
                artifact=RunArtifact(
                    id=artifact_id,
                    label="Report",
                    media_type="application/pdf",
                    filename=".",
                    disposition="attachment",
                ),
                body=iter([payload]),
            )

    async def authorize(request, action, *, run_id=None, intent=None):
        return "alice"

    environment = Environment(autoescape=select_autoescape())
    app = FastAPI()
    install_platform(app, environments=[environment])
    app.include_router(
        create_run_view_router(lambda: Port(), authorize, environment=environment)
    )
    with TestClient(app) as client:
        response = client.get("/runs/one/artifacts/bad%0D%0AX-Injected:%20yes")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition
    assert "X-Injected" not in disposition


@pytest.mark.parametrize(
    "media_type,body",
    [
        ("text/html", b"<script>alert(document.domain)</script>"),
        (
            "image/svg+xml",
            b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
        ),
    ],
)
def test_active_documents_are_not_served_inline(media_type, body):
    from app_factory import (
        RunArtifact,
        RunArtifactStream,
        create_run_view_router,
        install_platform,
    )
    from jinja2 import Environment, select_autoescape

    class Port:
        async def open_artifact(self, scope, run_id, artifact_id):
            return RunArtifactStream(
                artifact=RunArtifact(
                    id=artifact_id,
                    label="Preview",
                    media_type=media_type,
                    disposition="inline",
                    filename="preview",
                ),
                body=iter([body]),
            )

    async def authorize(request, action, *, run_id=None, intent=None):
        return "alice"

    environment = Environment(autoescape=select_autoescape())
    app = FastAPI()
    install_platform(app, environments=[environment])
    app.include_router(
        create_run_view_router(lambda: Port(), authorize, environment=environment)
    )
    with TestClient(app) as client:
        response = client.get("/runs/one/artifacts/preview")
    assert response.status_code == 200
    assert response.content == body
    assert "attachment" in response.headers["content-disposition"]
    assert "inline" not in response.headers["content-disposition"]


def test_run_errors_are_router_local_and_include_dependency_failures():
    from app_factory import RunError, create_run_router

    def dependency():
        raise RunError("unavailable", "Try again later")

    async def authorize(*args, **kwargs):
        return "alice"

    app = FastAPI()
    app.include_router(create_run_router(dependency, authorize))

    @app.get("/unrelated")
    def unrelated(value: int):
        return value

    with TestClient(app) as client:
        response = client.get("/runs")
        assert response.status_code == 503
        assert response.json() == {
            "version": "v1",
            "code": "unavailable",
            "message": "Try again later",
        }
        assert "detail" in client.get("/unrelated").json()
