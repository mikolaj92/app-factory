"""BOM reference host: app-factory + my-auth + my-usermanager.

Pins and override-dependencies come from this package's pyproject.toml
(aligned with ``bom/multi_user.toml``). The host owns session switching;
adapters own ceremonies, account/admin UI, and packaged invite admin.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Final, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from my_auth import PasskeyUser, RegistrationContext
from my_auth.fastapi import PasskeyCookies, PasskeyPaths, PasskeyRouteHooks
from my_auth.fastapi_htmx import PasskeyUiConfig, install_passkey_ui
from my_usermanager import Scope
from my_usermanager.adapters.fastapi_htmx import (
    CapabilityOption,
    CsrfContext,
    InvitationResult,
    PasskeyPanel,
    PermissionGrantRow,
    UserManagerUiConfig,
    UserRow,
    install_usermanager_ui,
)
from my_usermanager.invitations import InvitationError
from starlette.status import HTTP_303_SEE_OTHER, HTTP_403_FORBIDDEN

from app_factory.platform import (
    IDENTITY_AUTHENTICATED_SHELL,
    MenuItem,
    PlatformConfig,
    PlatformPaths,
    PlatformUser,
    apply_platform_context,
    build_platform_context,
    install_platform,
)
from demo_store import (
    ADMIN_ID,
    CSRF_HEADER,
    CSRF_TOKEN,
    MEMBER_ID,
    SESSION_COOKIE,
    DemoStore,
)

ROOT: Final = Path(__file__).resolve().parent
TEMPLATES: Final = Jinja2Templates(directory=str(ROOT / "templates"))
PASSKEY_PATHS: Final = PasskeyPaths()
PLATFORM_PATHS: Final = PlatformPaths(
    login=PASSKEY_PATHS.login_page,
    logout=PASSKEY_PATHS.logout,
    register=PASSKEY_PATHS.register_page,
    activation=PASSKEY_PATHS.activation_page,
    recovery=PASSKEY_PATHS.recovery_page,
    account="/account",
    credentials=PASSKEY_PATHS.credentials_page,
    admin_users="/admin/users",
    # Packaged invite form lives on the users page; POST remains /admin/users/invite.
    invite="/admin/users",
)


class _DemoCsrf:
    def token(self, _request: Request) -> str:
        return CSRF_TOKEN

    def validate(self, _request: Request, submitted_token: str) -> None:
        if submitted_token != CSRF_TOKEN:
            raise ValueError("invalid demo CSRF token")


def _session_user_id(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def _passkey_user(username: str) -> PasskeyUser:
    return PasskeyUser(
        user_id=username,
        user_handle=f"handle:{username}".encode(),
        name=username,
        display_name=username.title(),
    )


class _UmHooks:
    def __init__(
        self,
        demo: DemoStore,
        *,
        config: PlatformConfig,
        platform_user_fn,
    ) -> None:
        self._demo = demo
        self._config = config
        self._platform_user_fn = platform_user_fn

    def page_context(self, request: Request) -> dict:
        return dict(
            build_platform_context(
                self._config,
                user=self._platform_user_fn(request),
                current_path=request.url.path,
            )
        )

    def get_current_user(self, request: Request):
        user_id = _session_user_id(request) or ADMIN_ID
        return self._demo.subject(user_id)

    def require_admin(self, _request: Request, current_user) -> None:
        user = self._demo.users.get(current_user.user_id)
        if user is None or not user.is_admin:
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="admin required")

    def list_users(self, _request: Request, _current_user) -> tuple[UserRow, ...]:
        return self._demo.user_rows()

    def role_options(self, _request: Request, _current_user) -> tuple[str, ...]:
        return ("member", "admin")

    def capability_options(self, _request: Request, _current_user):
        return (
            CapabilityOption(
                permission="workflow.run",
                label="Run workflow",
                description="Demo capability",
                scope_type="workflow",
                scope_id="demo",
            ),
        )

    def set_user_disabled(
        self, _request: Request, _current_user, user_id: str, disabled: bool
    ) -> UserRow:
        um = self._demo.um_users.get(user_id)
        if um is None:
            raise ValueError("missing user")
        self._demo.um_users.update(
            replace(
                um,
                disabled=disabled,
                status="disabled" if disabled else "active",
            )
        )
        return next(row for row in self._demo.user_rows() if row.user_id == user_id)

    def grant_role(
        self, _request: Request, _current_user, user_id: str, role_name: str
    ) -> UserRow:
        self._demo.grants.add_role_grant(user_id, role_name, Scope.global_())
        return next(row for row in self._demo.user_rows() if row.user_id == user_id)

    def revoke_role(
        self, _request: Request, _current_user, user_id: str, role_name: str
    ) -> UserRow:
        self._demo.grants.remove_role_grant(user_id, role_name, Scope.global_())
        return next(row for row in self._demo.user_rows() if row.user_id == user_id)

    def grant_permission(
        self,
        _request: Request,
        _current_user,
        user_id: str,
        permission: PermissionGrantRow,
    ) -> UserRow:
        del permission
        return next(row for row in self._demo.user_rows() if row.user_id == user_id)

    def revoke_permission(
        self,
        _request: Request,
        _current_user,
        user_id: str,
        permission: PermissionGrantRow,
    ) -> UserRow:
        del permission
        return next(row for row in self._demo.user_rows() if row.user_id == user_id)

    def csrf_context(self, _request: Request) -> CsrfContext:
        return CsrfContext(
            hidden_inputs=(("_demo_csrf", CSRF_TOKEN),),
            headers={CSRF_HEADER: CSRF_TOKEN},
        )

    def after_user_disabled_changed(self, *_args) -> None:
        return None

    def render_passkey_panel(self, _request: Request, _current_user) -> PasskeyPanel:
        return PasskeyPanel(template_name="auth/_integration_panel.html", context={})

    def invite_user(
        self,
        _request: Request,
        current_user,
        username: str,
        email: str,
        role: str,
    ) -> InvitationResult:
        try:
            _invitation_id, token = self._demo.issue_invite(
                actor_id=current_user.user_id,
                username=username,
                email=email,
                role=role,
            )
        except InvitationError as exc:
            raise HTTPException(
                status_code=409, detail="invitation is unavailable"
            ) from exc
        return InvitationResult(
            activation_url=f"{PLATFORM_PATHS.activation}?capability={token}"
        )

    def reissue_invitation(
        self, _request: Request, current_user, invitation_id: str
    ) -> InvitationResult:
        try:
            _invitation_id, token = self._demo.reissue_invite(
                actor_id=current_user.user_id,
                invitation_id=invitation_id,
            )
        except InvitationError as exc:
            raise HTTPException(
                status_code=409, detail="invitation is unavailable"
            ) from exc
        return InvitationResult(
            activation_url=f"{PLATFORM_PATHS.activation}?capability={token}"
        )

    def revoke_invitation(
        self, _request: Request, current_user, invitation_id: str
    ) -> UserRow:
        try:
            revoked = self._demo.revoke_invite(
                actor_id=current_user.user_id,
                invitation_id=invitation_id,
            )
        except InvitationError as exc:
            raise HTTPException(
                status_code=409, detail="invitation is unavailable"
            ) from exc
        return next(
            row
            for row in self._demo.user_rows()
            if row.user_id == revoked.user_id
        )


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

    installed = install_platform(
        app,
        environments=[TEMPLATES.env],
        config=config,
    )
    platform = installed.ui

    def get_session_user(request: Request):
        user_id = _session_user_id(request)
        if not user_id:
            return None
        return demo.passkey_users.get(user_id)

    def prepare_registration(_request: Request, username: str):
        return demo.passkey_users.get(username) or _passkey_user(username)

    def prepare_registration_context(request: Request, flow_id: str, username: str):
        del request, flow_id
        user = demo.passkey_users.get(username) or _passkey_user(username)
        demo.passkey_users[user.user_id] = user
        return RegistrationContext(kind="bootstrap", user=user)

    def prepare_capability_registration_context(
        request: Request,
        flow_id: str,
        kind: Literal["invitation", "recovery"],
        capability: str,
    ):
        del request
        return demo.claim_capability(token=capability, flow_id=flow_id, kind=kind)

    def complete_registration(_request: Request, result):
        demo.passkey_users[result.user.user_id] = result.user
        return result.user

    def get_auth_user(user_id: str):
        return demo.passkey_users.get(user_id)

    def login(response: Response, _request: Request, user) -> None:
        response.set_cookie(SESSION_COOKIE, user.user_id, httponly=True, samesite="lax")

    def logout(response: Response, _request: Request) -> None:
        response.delete_cookie(SESSION_COOKIE)

    def registration_allowed(_request: Request) -> bool:
        return True

    async def unused_render_login(_request: Request) -> HTMLResponse:
        return HTMLResponse("replaced by install_passkey_ui")

    async def unused_render_register(
        _request: Request, *, bootstrap: bool
    ) -> HTMLResponse:
        del bootstrap
        return HTMLResponse("replaced by install_passkey_ui")

    hooks = PasskeyRouteHooks(
        get_session_user=get_session_user,
        prepare_registration=prepare_registration,
        complete_registration=complete_registration,
        get_auth_user=get_auth_user,
        login=login,
        logout=logout,
        registration_allowed=registration_allowed,
        render_login=unused_render_login,
        render_register=unused_render_register,
        prepare_registration_context=prepare_registration_context,
        prepare_capability_registration_context=prepare_capability_registration_context,
    )

    passkey_ui = install_passkey_ui(
        app,
        platform=platform,
        service=demo.passkey_service,
        hooks=hooks,
        config=PasskeyUiConfig(
            paths=PASSKEY_PATHS,
            cookies=PasskeyCookies(secure=False),
            csrf_header_name=CSRF_HEADER,
            csrf_token=lambda _request: CSRF_TOKEN,
            login_success_url="/",
            register_success_url="/",
            activation_success_url="/account",
            recovery_success_url="/login",
            show_registration_link=lambda _request: True,
        ),
    )
    # Host migration pattern: prefer identity shells over packaged shell.html.
    loader = passkey_ui.environment.loader
    if isinstance(loader, ChoiceLoader):
        loader.loaders.insert(
            0, FileSystemLoader(str(ROOT / "templates" / "my_auth_overrides"))
        )
    apply_platform_context(passkey_ui.environment, config)

    install_usermanager_ui(
        app,
        platform=platform,
        hooks=_UmHooks(demo, config=config, platform_user_fn=platform_user),
        config=UserManagerUiConfig(
            account_path=PLATFORM_PATHS.account,
            users_path=PLATFORM_PATHS.admin_users,
            invite_path="/admin/users/invite",
            login_url=PLATFORM_PATHS.login,
            logout_path=PLATFORM_PATHS.logout,
            csrf_protection=_DemoCsrf(),
            base_template=IDENTITY_AUTHENTICATED_SHELL,
        ),
        environment=TEMPLATES.env,
    )

    @app.middleware("http")
    async def bind_platform_context(request: Request, call_next):
        user = platform_user(request)
        for environment in (TEMPLATES.env, passkey_ui.environment):
            apply_platform_context(
                environment,
                config,
                user=user,
                current_path=request.url.path,
            )
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        user_id = _session_user_id(request)
        apply_platform_context(
            TEMPLATES.env,
            config,
            user=platform_user(request),
            current_path="/",
        )
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
