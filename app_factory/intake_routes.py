"""Opt-in single-form composition on RunPort; hosts own intents and execution."""

from collections.abc import Awaitable, Callable
from secrets import token_urlsafe
from typing import Any, Protocol

from fastapi import APIRouter, Depends, Request
from jinja2 import Environment
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartException

from app_factory.intake import IntakeError, IntakeSpec, IntakeSubmission
from app_factory.run_routes import RunAuthorization, _ERROR_STATUS
from app_factory.runs import Run, RunError, RunIntent, RunPort
from app_factory.uploads import UploadLimitExceeded, read_uploads_bounded


async def _bounded_request(request: Request, max_bytes: int) -> Request:
    # Bound the raw body before Starlette can spool files to temporary storage.
    # This also covers chunked requests and URL-encoded forms, not just files.
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > max_bytes:
            raise IntakeError({"": "Request size limit exceeded"}, status_code=413)
        body.extend(chunk)

    async def receive():
        return {"type": "http.request", "body": bytes(body), "more_body": False}

    return Request(request.scope, receive)


class IntakeCsrf(Protocol):
    def token(self, request: Request) -> str: ...
    def validate(self, request: Request, submitted_token: str) -> None: ...


IntakeBuilder = Callable[[Request, str, IntakeSubmission], Awaitable[RunIntent]]


def create_intake_router(
    port_dependency: Callable[..., Any],
    authorization: RunAuthorization,
    intent_builder: IntakeBuilder,
    *,
    spec: IntakeSpec,
    environment: Environment,
    csrf: IntakeCsrf,
    run_url: Callable[[Request, Run], str],
    prefix: str = "/intake",
) -> APIRouter:
    """Mount a GET form and POST start. ``run_url`` is a host-owned HTML page.

    Use SessionCsrfProtection (with SessionMiddleware), or a compatible adapter.
    The host RunPort owns atomic, scope-bound durable idempotency. The builder
    must produce stable intents on retries. Authorization is called before the
    builder (intent=None) and again with its intent before any port operation.
    Builders own domain/format validation and any durable upload storage; return
    refs in RunIntent.input, never rely on temporary UploadFile paths. Repeated
    builds must reuse refs (submission.idempotency_key is provided) and clean up
    host-owned data on failure according to product policy.

    The environment must enable HTML autoescaping and load factory templates.
    Override the component templates to compose a host shell/copy. Include the
    existing file_upload_boot with HTMX/Alpine for enhanced uploads; native POST
    needs none of them. Status target is a hook, not an automatic polling loop.
    """
    router = APIRouter(prefix=prefix, tags=["intake"])

    def form(request, *, values=None, key=None, errors=None, status_code=200):
        html = environment.get_template("app_factory/components/intake.html").render(
            request=request,
            spec=spec,
            action=request.url.path,
            values=values or {},
            csrf_token=csrf.token(request),
            idempotency_key=key or token_urlsafe(32),
            errors=errors or {},
        )
        # HTMX's default response handling does not swap 4xx/5xx. Return a
        # rendered correction form with 200; native requests retain error codes.
        return HTMLResponse(
            html,
            status_code=(200 if is_htmx(request) else status_code),
            headers={
                "Cache-Control": "no-store",
                "Vary": "HX-Request",
                "HX-Retarget": f"#{spec.id}",
                "HX-Reswap": "outerHTML",
            },
        )

    def is_htmx(request):
        return request.headers.get("HX-Request", "").lower() == "true"

    @router.get("", response_class=HTMLResponse)
    async def show(request: Request):
        try:
            await authorization(request, "create")
        except RunError as exc:
            return form(
                request,
                errors={"": exc.response.message},
                status_code=_ERROR_STATUS[exc.response.code],
            )
        return form(request)

    @router.post("")
    async def start(request: Request, port: RunPort = Depends(port_dependency)):
        values = {}
        key = None
        try:
            scope = await authorization(request, "create")
            bounded = await _bounded_request(request, spec.max_request_bytes)
            # Count and size are checked again below with field-local messages.
            async with bounded.form(
                max_files=spec.files.max_files if spec.files else 0,
                max_fields=len(spec.fields) + 3,
            ) as data:
                file_name = spec.files.name if spec.files else None
                allowed = {f.name for f in spec.fields} | {
                    "csrf_token",
                    "idempotency_key",
                }
                if file_name:
                    allowed.add(file_name)
                if any(
                    name not in allowed
                    or (
                        name != file_name
                        and (
                            len(data.getlist(name)) != 1
                            or not isinstance(data[name], str)
                        )
                    )
                    for name in data
                ):
                    raise IntakeError({"": "Unexpected or repeated inputs"})
                try:
                    csrf.validate(request, data.get("csrf_token", ""))
                except PermissionError:
                    raise IntakeError(
                        {"": "Invalid CSRF token"}, status_code=403
                    ) from None
                key = data.get("idempotency_key", "")
                if not key.strip() or len(key) > 255:
                    key = None
                    raise IntakeError({"": "Invalid submission key"})
                values = {field.name: data.get(field.name, "") for field in spec.fields}
                errors = {}
                for field in spec.fields:
                    value = values[field.name]
                    if field.required and not value.strip():
                        errors[field.name] = "This field is required"
                    elif len(value) > field.max_length:
                        errors[field.name] = (
                            f"Use at most {field.max_length} characters"
                        )
                    elif (
                        field.kind == "select"
                        and value
                        and value not in dict(field.options)
                    ):
                        errors[field.name] = "Choose a listed option"
                if errors:
                    raise IntakeError(errors)
                uploads = ()
                if spec.files:
                    raw = data.getlist(file_name)
                    if any(
                        not isinstance(item, UploadFile) and item != "" for item in raw
                    ):
                        raise IntakeError({file_name: "Invalid file input"})
                    raw = [
                        item
                        for item in raw
                        if isinstance(item, UploadFile) and item.filename
                    ]
                    if spec.files.required and not raw:
                        raise IntakeError({file_name: "Choose at least one file"})
                    try:
                        uploads = await read_uploads_bounded(
                            raw,
                            max_files=spec.files.max_files,
                            max_file_bytes=spec.files.max_file_bytes,
                            max_total_bytes=spec.files.max_total_bytes,
                        )
                    except UploadLimitExceeded:
                        raise IntakeError(
                            {file_name: "Upload limit exceeded"}, status_code=413
                        ) from None
                intent = await intent_builder(
                    request, scope, IntakeSubmission(values, key, uploads)
                )
                authorized_scope = await authorization(request, "create", intent=intent)
                if authorized_scope != scope:
                    raise RunError("forbidden", "Authorization scope changed")
                run = await port.create_intent(scope, intent, idempotency_key=key)
        except (HTTPException, MultiPartException):
            # Never expose parser internals or uploaded content in errors.
            return form(
                request,
                values=values,
                key=key,
                errors={
                    spec.files.name
                    if spec.files
                    else "": "Upload limit exceeded or malformed form"
                },
                status_code=422,
            )
        except IntakeError as exc:
            return form(
                request,
                values=values,
                key=key,
                errors=exc.errors,
                status_code=exc.status_code,
            )
        except RunError as exc:
            return form(
                request,
                values=values,
                key=key,
                errors={"": exc.response.message},
                status_code=_ERROR_STATUS[exc.response.code],
            )
        url = run_url(request, run)
        if request.headers.get("HX-Request", "").lower() != "true":
            return RedirectResponse(url, status_code=303)
        return HTMLResponse(
            environment.get_template(
                "app_factory/components/intake_receipt.html"
            ).render(
                request=request,
                spec=spec,
                run=run,
                values=values,
                run_url=url,
                uploads=uploads,
            ),
            headers={
                "Cache-Control": "no-store",
                "Vary": "HX-Request",
                "HX-Retarget": f"#{spec.id}",
                "HX-Reswap": "outerHTML",
            },
        )

    return router
