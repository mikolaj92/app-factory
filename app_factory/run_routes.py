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
