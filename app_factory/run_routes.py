"""Opt-in run HTTP transport; no scheduling or storage."""

from collections.abc import Callable
from typing import Any, Protocol

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse

from app_factory.runs import (
    Run,
    RunAction,
    RunArtifacts,
    RunError,
    RunErrorResponse,
    RunIntent,
    RunPage,
    RunPort,
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

    router = APIRouter(prefix=prefix, tags=["run-views"])

    def is_htmx(request: Request) -> bool:
        return request.headers.get("HX-Request", "").lower() == "true"

    def is_history_restore(request: Request) -> bool:
        return request.headers.get("HX-History-Restore-Request", "").lower() == "true"

    def want_fragment(request: Request) -> bool:
        return is_htmx(request) and not is_history_restore(request)

    def base_headers(*, retry_after: int | None = None) -> dict[str, str]:
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
        headers = base_headers(retry_after=retry_after)
        values = dict(getattr(request.state, "app_factory_platform_context", {}) or {})
        values.update(context)
        values["request"] = request
        if want_fragment(request):
            html = environment.get_template(fragment_template).render(**values)
            return HTMLResponse(
                html,
                status_code=200 if status_code >= 400 else status_code,
                headers=headers,
            )
        values["run_fragment"] = fragment_template
        html = environment.get_template("app_factory/run_page.html").render(**values)
        return HTMLResponse(html, status_code=status_code, headers=headers)

    def error_response(
        request: Request,
        *,
        target_id: str,
        exc: RunError,
        poll_url: str,
    ) -> HTMLResponse:
        code = exc.response.code
        state = _STATE.get(code, "transient-error")
        status = _ERROR_STATUS.get(code, 503)
        retry_after = exc.response.retry_after
        poll_seconds = retry_after if code == "unavailable" and retry_after else None
        context = {
            "target_id": target_id,
            "state": state,
            "message": exc.response.message,
            "poll_url": poll_url,
            "poll_seconds": poll_seconds,
        }
        return page_or_fragment(
            request,
            fragment_template="app_factory/components/run_state.html",
            context=context,
            status_code=status,
            retry_after=retry_after,
        )

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
        context = {
            "page": page,
            "run_links": run_links,
            "next_url": (
                history_next_url(request, page.next_cursor)
                if page.next_cursor
                else None
            ),
        }
        return page_or_fragment(
            request,
            fragment_template="app_factory/components/run_history.html",
            context=context,
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
        context = {
            "run": run,
            "poll_url": poll_url,
            "poll_seconds": seconds,
        }
        return page_or_fragment(
            request,
            fragment_template="app_factory/components/run_detail.html",
            context=context,
            retry_after=seconds,
        )

    return router
