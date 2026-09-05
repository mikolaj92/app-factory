"""Signed-session BOM host behind a reverse-proxy prefix.

Structurally different from ``app.py``: ``SessionMiddleware`` +
``PlatformPaths.root`` + session CSRF. Same ``install_identity_adapters``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from my_auth.fastapi import PasskeyCookies
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_303_SEE_OTHER

from app_factory import template_response
from app_factory.adapters import (
    PasskeyBinding,
    UserManagerBinding,
    install_identity_adapters,
)
from app_factory.csrf import SessionCsrfProtection
from app_factory.platform import (
    MenuGroup,
    MenuItem,
    PlatformConfig,
    PlatformPaths,
    PlatformUser,
)
from demo_store import ADMIN_ID, MEMBER_ID, DemoStore
from policy import DemoPasskeyHooks, DemoUserManagerHooks

ROOT: Final = Path(__file__).resolve().parent
TEMPLATES: Final = Jinja2Templates(directory=str(ROOT / "templates"))
PLATFORM_PATHS: Final = PlatformPaths(root="/portal")
SESSION_KEY: Final = "portal_user_id"
CSRF = SessionCsrfProtection(session_key="portal_csrf")


def _session_user_id(request: Request) -> str | None:
    if "session" not in request.scope:
        return None
    user_id = request.session.get(SESSION_KEY)
    return user_id if isinstance(user_id, str) and user_id else None


def _login_user(_response: Response, request: Request, user) -> None:
    request.session[SESSION_KEY] = user.user_id
    _ = CSRF.token(request)


def _logout_user(_response: Response, request: Request) -> None:
    request.session.clear()


def create_app(store: DemoStore | None = None) -> FastAPI:
    demo = store or DemoStore()
    app = FastAPI(title="Rooted portal BOM host", docs_url=None)
    app.state.demo_store = demo

    resolved = PLATFORM_PATHS.resolved()
    config = PlatformConfig(
        app_name="Portal",
        brand_href="/portal/",
        brand_meta="rooted",
        menu=(
            MenuGroup(
                "Workspace",
                (MenuItem("Queue", "/portal/", key="queue"),),
            ),
        ),
        paths=PLATFORM_PATHS,
        enable_account=True,
        enable_credentials=True,
        enable_admin_users=True,
        enable_invite=True,
        show_register=False,
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
            csrf_token=CSRF.token,
            login_success_url="/portal/",
            register_success_url="/portal/",
            activation_success_url=resolved.account,
            recovery_success_url=resolved.login,
        ),
        usermanager=UserManagerBinding(
            hooks=DemoUserManagerHooks(
                demo,
                session_user_id=_session_user_id,
                activation_page=resolved.activation,
                csrf_token=CSRF.token,
                csrf_header="X-CSRF-Token",
            ),
            csrf_protection=CSRF,
            environment=TEMPLATES.env,
        ),
        current_user=platform_user,
    )

    # Last-added middleware runs first: session must wrap request-context.
    app.add_middleware(SessionMiddleware, secret_key="bom-portal-demo", https_only=False)

    @app.get("/portal/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        user_id = _session_user_id(request)
        return template_response(
            TEMPLATES.env,
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
                "paths": resolved,
                "demo_root": "/portal",
            },
        )

    @app.post("/portal/demo/as/{user_id}")
    def switch_user(request: Request, user_id: str) -> RedirectResponse:
        if user_id in demo.users:
            request.session[SESSION_KEY] = user_id
            _ = CSRF.token(request)
        return RedirectResponse("/portal/", status_code=HTTP_303_SEE_OTHER)

    @app.post("/portal/demo/recovery/{user_id}")
    def issue_recovery(user_id: str, request: Request) -> RedirectResponse:
        actor = _session_user_id(request) or ADMIN_ID
        token = demo.issue_recovery(subject=user_id, issued_by=actor)
        response = RedirectResponse("/portal/", status_code=HTTP_303_SEE_OTHER)
        response.headers["X-Demo-Recovery-URL"] = (
            f"{resolved.recovery}?capability={token}"
        )
        return response

    return app


app = create_app()
