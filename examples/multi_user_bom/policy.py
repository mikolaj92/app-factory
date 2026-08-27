"""Host-owned persistence and RBAC hooks shared by the two reference hosts.

Session transport differs (cookie vs signed session). Ceremony and user
lifecycle stay in my-auth / my-usermanager.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Literal

from fastapi import HTTPException, Request, Response
from my_auth import PasskeyUser, RegistrationContext
from my_usermanager import Scope
from my_usermanager.adapters.fastapi_htmx import (
    CapabilityOption,
    CsrfContext,
    InvitationResult,
    PasskeyPanel,
    PermissionGrantRow,
    UserRow,
)
from my_usermanager.invitations import InvitationError
from starlette.status import HTTP_403_FORBIDDEN

from demo_store import ADMIN_ID, CSRF_HEADER, CSRF_TOKEN, DemoStore

SessionUserId = Callable[[Request], str | None]
LoginUser = Callable[[Response, Request, PasskeyUser], None]
LogoutUser = Callable[[Response, Request], None]


def passkey_user(username: str) -> PasskeyUser:
    return PasskeyUser(
        user_id=username,
        user_handle=f"handle:{username}".encode(),
        name=username,
        display_name=username.title(),
    )


class DemoPasskeyHooks:
    """In-memory passkey policy; hosts bind session get/set only."""

    def __init__(
        self,
        demo: DemoStore,
        *,
        session_user_id: SessionUserId,
        login_user: LoginUser,
        logout_user: LogoutUser,
    ) -> None:
        self._demo = demo
        self._session_user_id = session_user_id
        self._login_user = login_user
        self._logout_user = logout_user

    def get_session_user(self, request: Request):
        user_id = self._session_user_id(request)
        if not user_id:
            return None
        return self._demo.passkey_users.get(user_id)

    def prepare_registration(self, _request: Request, username: str):
        return self._demo.passkey_users.get(username) or passkey_user(username)

    def prepare_registration_context(
        self, request: Request, flow_id: str, username: str
    ):
        del request, flow_id
        user = self._demo.passkey_users.get(username) or passkey_user(username)
        self._demo.passkey_users[user.user_id] = user
        return RegistrationContext(kind="bootstrap", user=user)

    def prepare_capability_registration_context(
        self,
        request: Request,
        flow_id: str,
        kind: Literal["invitation", "recovery"],
        capability: str,
    ):
        del request
        return self._demo.claim_capability(
            token=capability, flow_id=flow_id, kind=kind
        )

    def complete_registration(self, _request: Request, result):
        self._demo.passkey_users[result.user.user_id] = result.user
        return result.user

    def get_auth_user(self, user_id: str):
        return self._demo.passkey_users.get(user_id)

    def login(self, response: Response, request: Request, user) -> None:
        self._login_user(response, request, user)

    def logout(self, response: Response, request: Request) -> None:
        self._logout_user(response, request)

    def registration_allowed(self, _request: Request) -> bool:
        return True


class DemoUserManagerHooks:
    """Demo RBAC catalog and invitation persistence. No installer glue."""

    def __init__(
        self,
        demo: DemoStore,
        *,
        session_user_id: SessionUserId,
        activation_page: str,
        csrf_token: str | Callable[[Request], str] = CSRF_TOKEN,
        csrf_header: str = CSRF_HEADER,
    ) -> None:
        self._demo = demo
        self._session_user_id = session_user_id
        self._activation_page = activation_page
        self._csrf_token = csrf_token
        self._csrf_header = csrf_header

    def get_current_user(self, request: Request):
        user_id = self._session_user_id(request)
        if not user_id:
            return None
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

    def csrf_context(self, request: Request) -> CsrfContext:
        token = (
            self._csrf_token(request)
            if callable(self._csrf_token)
            else self._csrf_token
        )
        return CsrfContext(
            hidden_inputs=(("_demo_csrf", token),),
            headers={self._csrf_header: token},
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
            activation_url=f"{self._activation_page}?capability={token}"
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
            activation_url=f"{self._activation_page}?capability={token}"
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
            row for row in self._demo.user_rows() if row.user_id == revoked.user_id
        )


# Re-export for hosts that still want the seeded admin id.
__all__ = [
    "ADMIN_ID",
    "DemoPasskeyHooks",
    "DemoUserManagerHooks",
    "passkey_user",
]
