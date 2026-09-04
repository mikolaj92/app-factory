"""Cookie-session BOM host: default paths, in-memory stores.

Uses :func:`install_identity_adapters` so this file owns session transport,
RBAC catalog, and persistence only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from my_auth.fastapi import PasskeyCookies
from starlette.status import HTTP_303_SEE_OTHER

from app_factory.adapters import (
    PasskeyBinding,
    UserManagerBinding,
    install_identity_adapters,
)
from app_factory.platform import (
    MenuItem,
    PlatformConfig,
    PlatformPaths,
    PlatformUser,
)
from demo_store import (
    ADMIN_ID,
    CSRF_HEADER,
    CSRF_TOKEN,
    MEMBER_ID,
    SESSION_COOKIE,
    DemoStore,
)
from policy import DemoPasskeyHooks, DemoUserManagerHooks

ROOT: Final = Path(__file__).resolve().parent
TEMPLATES: Final = Jinja2Templates(directory=str(ROOT / "templates"))
PLATFORM_PATHS: Final = PlatformPaths()


class _DemoCsrf:
    def token(self, _request: Request) -> str:
        return CSRF_TOKEN

    def validate(self, _request: Request, submitted_token: str) -> None:
        if submitted_token != CSRF_TOKEN:
            raise ValueError("invalid demo CSRF token")


def _session_user_id(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def _login_user(response: Response, _request: Request, user) -> None:
    response.set_cookie(SESSION_COOKIE, user.user_id, httponly=True, samesite="lax")


def _logout_user(response: Response, _request: Request) -> None:
    response.delete_cookie(SESSION_COOKIE)


def create_app(store: DemoStore | None = None) -> FastAPI:
    demo = store or DemoStore()
    app = FastAPI(title="Multi-user platform BOM example", docs_url=None)
    app.state.demo_store = demo

    config = PlatformConfig(
        app_name="BOM demo",
        brand_href="/",
        brand_meta="multi-user",
        menu=(MenuItem("Home", "/", key="home"),),
        paths=PLATFORM_PATHS,
        enable_account=True,
        enable_credentials=True,
        enable_admin_users=True,
        enable_invite=True,
        show_register=True,
    )

    def platform_user(request: Request) -> PlatformUser | None:
        user_id = _session_user_id(request)
        if not user_id:
            return None
        user = demo.users.get(user_id)
        if user is None:
            return None
        return PlatformUser(
            display_name=user.display_name,
            is_admin=user.is_admin,
            user_id=user.user_id,
        )

    install_identity_adapters(
        app,
        environments=[TEMPLATES.env],
        config=config,
        passkey=PasskeyBinding(
            service=demo.passkey_service,
            hooks=DemoPasskeyHooks(
                demo,
                session_user_id=_session_user_id,
                login_user=_login_user,
                logout_user=_logout_user,
            ),
            cookies=PasskeyCookies(secure=False),
            csrf_header_name=CSRF_HEADER,
            csrf_token=lambda _request: CSRF_TOKEN,
            login_success_url="/",
            register_success_url="/",
            activation_success_url=PLATFORM_PATHS.account,
            recovery_success_url=PLATFORM_PATHS.login,
        ),
        usermanager=UserManagerBinding(
            hooks=DemoUserManagerHooks(
                demo,
                session_user_id=_session_user_id,
                activation_page=PLATFORM_PATHS.activation,
            ),
            csrf_protection=_DemoCsrf(),
            environment=TEMPLATES.env,
        ),
        current_user=platform_user,
    )

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        user_id = _session_user_id(request)
        return TEMPLATES.TemplateResponse(
            request,
            "home.html",
            {
                "session_user": user_id,
                "admin_id": ADMIN_ID,
                "member_id": MEMBER_ID,
                "admin_credentials": len(demo.credentials_for(ADMIN_ID)),
                "member_credentials": len(demo.credentials_for(MEMBER_ID)),
                "issued_invites": list(demo.issued_invites),
                "issued_recoveries": list(demo.issued_recoveries),
                "paths": PLATFORM_PATHS,
                "demo_root": "",
            },
        )

    @app.post("/demo/as/{user_id}")
    def switch_user(user_id: str) -> RedirectResponse:
        response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
        if user_id in demo.users:
            response.set_cookie(SESSION_COOKIE, user_id, httponly=True, samesite="lax")
        return response

    @app.post("/demo/recovery/{user_id}")
    def issue_recovery(user_id: str, request: Request) -> RedirectResponse:
        actor = _session_user_id(request) or ADMIN_ID
        token = demo.issue_recovery(subject=user_id, issued_by=actor)
        response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
        response.headers["X-Demo-Recovery-URL"] = (
            f"{PLATFORM_PATHS.recovery}?capability={token}"
        )
        return response

    return app


app = create_app()
