"""Reference hosts only: no in-memory run backend ships in app_factory."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient


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
                    status="queued",
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
                status="queued",
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
                        name="Output",
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
                status={0: "queued", 9: "cancelled"}[job["phase"]],
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
                        name="Output",
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
        "queued",
        "running",
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
