"""Opt-in run HTTP transport; no scheduling or storage."""

from collections.abc import Callable
from hmac import compare_digest
from pathlib import PurePosixPath
from typing import Any, Protocol
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse, StreamingResponse

from app_factory.runs import (
    Run,
    RunAction,
    RunArtifact,
    RunArtifacts,
    RunArtifactStream,
    RunError,
    RunErrorResponse,
    RunIntent,
    RunPage,
    RunPort,
    safe_external_href,
)

_ERROR_STATUS = {
    "unauthorized": 401,
    "forbidden": 403,
    "not_found": 404,
    "conflict": 409,
    "invalid_request": 422,
    "unavailable": 503,
    "stale_version": 409,
}
_TERMINAL_SUCCESS = "succeeded"
_ACTIVE_MEDIA = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
        "image/svg+xml",
        "text/xml",
        "application/xml",
        "application/javascript",
        "text/javascript",
        "application/xhtml",
    }
)


def _filename_piece(value: str | None) -> str:
    if not value:
        return ""
    cleaned = []
    for ch in value:
        if ord(ch) < 32 or ord(ch) == 127:
            break
        cleaned.append(ch)
    name = PurePosixPath("".join(cleaned).replace("\\", "/")).name.strip().strip(".")
    if not name or name in {".", ".."}:
        return ""
    return name[:180]


def safe_artifact_filename(value: str | None, *, fallback: str = "download") -> str:
    return _filename_piece(value) or _filename_piece(fallback) or "download"


def is_active_document(media_type: str) -> bool:
    base = media_type.split(";", 1)[0].strip().lower()
    return base in _ACTIVE_MEDIA or base.endswith("+xml")


def artifact_kind(item: RunArtifact) -> str:
    if safe_external_href(item.href):
        return "external"
    if item.filename or item.disposition or item.size is not None or item.digest:
        return "download"
    return "metadata"


def artifact_download_url(prefix: str, run_id: str, artifact_id: str) -> str:
    base = prefix.rstrip("/") or ""
    return f"{base}/{run_id}/artifacts/{artifact_id}"


def content_disposition(filename: str, disposition: str | None) -> str:
    kind = disposition if disposition in {"inline", "attachment"} else "attachment"
    safe = safe_artifact_filename(filename)
    ascii_name = safe.encode("ascii", "ignore").decode("ascii") or "download"
    ascii_name = ascii_name.replace("\\", "_").replace('"', "")
    encoded = quote(safe, safe="")
    header = f'{kind}; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded}'
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in header):
        return 'attachment; filename="download"'
    return header


def artifact_response(stream: object, artifact_id: str) -> StreamingResponse:
    if not isinstance(stream, RunArtifactStream):
        raise RunError("unavailable", "Invalid artifact stream")
    artifact = stream.artifact
    if artifact.id != artifact_id:
        raise RunError("not_found", "Artifact missing")
    expected = stream.digest or artifact.digest
    actual = artifact.digest
    if expected and actual and (
        len(expected) != len(actual) or not compare_digest(expected, actual)
    ):
        raise RunError("conflict", "Artifact digest mismatch")
    filename = safe_artifact_filename(artifact.filename or artifact.label)
    media_type = artifact.media_type or "application/octet-stream"
    if "\r" in media_type or "\n" in media_type or ";" in media_type:
        media_type = "application/octet-stream"
    disposition = artifact.disposition
    if is_active_document(media_type):
        disposition = "attachment"
    body = stream.body
    if isinstance(body, (bytes, bytearray, memoryview)):
        body = iter((bytes(body),))
    return StreamingResponse(
        body,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": content_disposition(filename, disposition),
        },
    )


class _RunRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                return await handler(request)
            except RequestValidationError:
                error = RunErrorResponse(
                    code="invalid_request",
                    message="Invalid run request",
                )
                return JSONResponse(error.model_dump(mode="json", exclude_none=True), status_code=422)
            except RunError as exc:
                return JSONResponse(
                    exc.response.model_dump(mode="json", exclude_none=True),
                    status_code=_ERROR_STATUS[exc.response.code],
                    headers=(
                        {"Retry-After": str(exc.response.retry_after)}
                        if exc.response.retry_after else None
                    ),
                )

        return handle


class RunAuthorization(Protocol):
    """Authorize before any port call and return a host-defined access scope.

    Raise RunError on denial. History uses read with run_id=None. The port
    must enforce the returned scope (not merely filter already-paged results).
    Authentication/session resolution and product RBAC remain host-owned.
    """

    async def __call__(
        self,
        request: Request,
        action: RunAction,
        *,
        run_id: str | None = None,
        intent: RunIntent | None = None,
    ) -> str: ...


def create_run_router(
    port_dependency: Callable[..., Any],
    authorization: RunAuthorization,
    *,
    prefix: str = "/runs",
) -> APIRouter:
    """Supply an ordinary FastAPI dependency and mandatory async policy.

    Dependencies may resolve a request-local port and use nested Depends.
    Hosts using cookie sessions must also install their CSRF middleware.
    """
    router = APIRouter(
        prefix=prefix,
        tags=["runs"],
        route_class=_RunRoute,
        responses={
            status: {"model": RunErrorResponse} for status in _ERROR_STATUS.values()
        },
    )

    @router.post("", response_model=Run, status_code=202)
    async def create(
        request: Request,
        intent: RunIntent,
        idempotency_key: str = Header(min_length=1, max_length=255, pattern=r"\S"),
        port: RunPort = Depends(port_dependency),
    ) -> Run:
        scope = await authorization(request, "create", intent=intent)
        return await port.create_intent(scope, intent, idempotency_key=idempotency_key)

    @router.get("", response_model=RunPage)
    async def history(
        request: Request,
        cursor: str | None = Query(default=None, min_length=1, max_length=2048),
        limit: int = Query(default=20, ge=1, le=100),
        port: RunPort = Depends(port_dependency),
    ) -> RunPage:
        scope = await authorization(request, "read")
        return await port.list_runs(scope, cursor=cursor, limit=limit)

    @router.get("/{run_id}", response_model=Run)
    async def read(
        request: Request,
        run_id: str,
        port: RunPort = Depends(port_dependency),
    ) -> Run:
        scope = await authorization(request, "read", run_id=run_id)
        return await port.get_run(scope, run_id)

    @router.post("/{run_id}/cancel", response_model=Run, status_code=202)
    async def cancel(
        request: Request,
        run_id: str,
        port: RunPort = Depends(port_dependency),
    ) -> Run:
        scope = await authorization(request, "cancel", run_id=run_id)
        return await port.request_cancel(scope, run_id)

    @router.get("/{run_id}/artifacts", response_model=RunArtifacts)
    async def artifacts(
        request: Request,
        run_id: str,
        port: RunPort = Depends(port_dependency),
    ) -> RunArtifacts:
        scope = await authorization(request, "artifact", run_id=run_id)
        return await port.list_artifacts(scope, run_id)

    @router.get("/{run_id}/artifacts/{artifact_id}")
    async def download(
        request: Request,
        run_id: str,
        artifact_id: str,
        port: RunPort = Depends(port_dependency),
    ) -> StreamingResponse:
        scope = await authorization(request, "artifact", run_id=run_id)
        opener = getattr(port, "open_artifact", None)
        if opener is None:
            raise RunError("not_found", "Artifact missing")
        return artifact_response(await opener(scope, run_id, artifact_id), artifact_id)

    return router


def create_run_view_router(
    port_dependency: Callable[..., Any],
    authorization: RunAuthorization,
    *,
    environment: Any,
    prefix: str = "/runs",
) -> APIRouter:
    """Opt-in HTML/HTMX run detail and history; JSON API stays on create_run_router."""
    from urllib.parse import urlencode

    from fastapi.responses import HTMLResponse
    from jinja2 import Environment

    from app_factory.responses import template_response, wants_htmx_fragment

    if not isinstance(environment, Environment):
        raise TypeError("environment must be a Jinja2 Environment")

    _STATE = {
        "unauthorized": "unauthorized",
        "forbidden": "unauthorized",
        "not_found": "not-found",
        "unavailable": "transient-error",
        "stale_version": "stale-version",
        "invalid_request": "invalid-request",
        "conflict": "stale-version",
    }
    _TERMINAL = frozenset({"succeeded", "failed", "cancelled"})

    def target_for(request: Request) -> str:
        base = prefix.rstrip("/") or ""
        path = request.url.path.rstrip("/")
        rest = (
            path[len(base):].lstrip("/")
            if base and path.startswith(base)
            else path.lstrip("/")
        )
        return "run-history" if rest == "" else "run-detail"

    def headers_for(*, retry_after: int | None = None) -> dict[str, str]:
        headers = {
            "Cache-Control": "no-store",
            "Vary": "HX-Request, HX-History-Restore-Request",
        }
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        return headers

    def page_or_fragment(
        request: Request,
        *,
        fragment_template: str,
        context: dict[str, Any],
        status_code: int = 200,
        retry_after: int | None = None,
    ) -> HTMLResponse:
        fragment = wants_htmx_fragment(request)
        response = template_response(
            environment,
            request,
            "app_factory/run_page.html",
            {**context, "run_fragment": fragment_template},
            fragment_template=fragment_template,
            status_code=200 if fragment and status_code >= 400 else status_code,
            headers=headers_for(retry_after=retry_after),
        )
        return response

    def error_response(
        request: Request,
        *,
        target_id: str,
        exc: RunError,
        poll_url: str,
    ) -> HTMLResponse:
        code = exc.response.code
        retry_after = exc.response.retry_after
        return page_or_fragment(
            request,
            fragment_template="app_factory/components/run_state.html",
            context={
                "target_id": target_id,
                "state": _STATE.get(code, "transient-error"),
                "message": exc.response.message,
                "poll_url": poll_url,
                "poll_seconds": (
                    retry_after if code == "unavailable" and retry_after else None
                ),
            },
            status_code=_ERROR_STATUS.get(code, 503),
            retry_after=retry_after,
        )

    class _RunViewRoute(APIRoute):
        def get_route_handler(self):
            handler = super().get_route_handler()

            async def handle(request: Request):
                try:
                    return await handler(request)
                except RunError as exc:
                    return error_response(
                        request,
                        target_id=target_for(request),
                        exc=exc,
                        poll_url=str(request.url.path),
                    )

            return handle

    router = APIRouter(prefix=prefix, tags=["run-views"], route_class=_RunViewRoute)

    def poll_seconds_for(run: Run) -> int | None:
        if run.status in _TERMINAL:
            return None
        return run.retry_after or 2

    def history_next_url(request: Request, next_cursor: str) -> str:
        pairs: list[tuple[str, str]] = []
        for key, value in request.query_params.multi_items():
            if key == "cursor":
                continue
            pairs.append((key, value))
        pairs.append(("cursor", next_cursor))
        return f"{request.url.path}?{urlencode(pairs)}"

    @router.get("", response_class=HTMLResponse)
    async def history(
        request: Request,
        port: RunPort = Depends(port_dependency),
    ) -> HTMLResponse:
        poll_url = str(request.url.path)
        try:
            cursor = request.query_params.get("cursor")
            limit_raw = request.query_params.get("limit", "20")
            try:
                limit = int(limit_raw)
            except ValueError as exc:
                raise RunError("invalid_request", "Invalid limit") from exc
            if limit < 1 or limit > 100:
                raise RunError("invalid_request", "Invalid limit")
            if "cursor" in request.query_params and (cursor is None or cursor == ""):
                raise RunError("invalid_request", "Invalid cursor")
            scope = await authorization(request, "read")
            page = await port.list_runs(scope, cursor=cursor, limit=limit)
        except RunError as exc:
            return error_response(
                request, target_id="run-history", exc=exc, poll_url=poll_url
            )

        run_links = {run.id: f"{prefix.rstrip('/')}/{run.id}" for run in page.items}
        return page_or_fragment(
            request,
            fragment_template="app_factory/components/run_history.html",
            context={
                "page": page,
                "run_links": run_links,
                "next_url": (
                    history_next_url(request, page.next_cursor)
                    if page.next_cursor
                    else None
                ),
            },
        )

    @router.get("/{run_id}", response_class=HTMLResponse)
    async def detail(
        request: Request,
        run_id: str,
        port: RunPort = Depends(port_dependency),
    ) -> HTMLResponse:
        poll_url = f"{prefix.rstrip('/')}/{run_id}"
        try:
            scope = await authorization(request, "read", run_id=run_id)
            run = await port.get_run(scope, run_id)
        except RunError as exc:
            return error_response(
                request, target_id="run-detail", exc=exc, poll_url=poll_url
            )

        seconds = poll_seconds_for(run)
        result = None
        if run.status == _TERMINAL_SUCCESS:
            getter = getattr(port, "get_result", None)
            if getter is not None:
                try:
                    result = await getter(scope, run_id)
                except RunError as exc:
                    return error_response(
                        request, target_id="run-detail", exc=exc, poll_url=poll_url
                    )
        return page_or_fragment(
            request,
            fragment_template="app_factory/components/run_detail.html",
            context={
                "run": run,
                "poll_url": poll_url,
                "poll_seconds": seconds,
                "result": result,
                "artifact_kind": artifact_kind,
                "safe_href": safe_external_href,
                "download_url": lambda item: artifact_download_url(
                    prefix, run_id, item.id
                ),
            },
            retry_after=seconds,
        )

    @router.get("/{run_id}/artifacts/{artifact_id}")
    async def download(
        request: Request,
        run_id: str,
        artifact_id: str,
        port: RunPort = Depends(port_dependency),
    ):
        poll_url = f"{prefix.rstrip('/')}/{run_id}/artifacts/{artifact_id}"
        try:
            scope = await authorization(request, "artifact", run_id=run_id)
            opener = getattr(port, "open_artifact", None)
            if opener is None:
                raise RunError("not_found", "Artifact missing")
            return artifact_response(
                await opener(scope, run_id, artifact_id), artifact_id
            )
        except RunError as exc:
            return error_response(
                request, target_id="run-detail", exc=exc, poll_url=poll_url
            )

    return router
