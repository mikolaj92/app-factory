"""One generic install path on two structurally different hosts."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from jinja2 import DictLoader, Environment
from my_auth.fastapi import PasskeyCookies

from app import SESSION_COOKIE, create_app
from app_factory.adapters import (
    IdentityAdapterConflict,
    PasskeyBinding,
    UserManagerBinding,
    install_identity_adapters,
)
from app_factory.platform import PlatformConfig, PlatformPaths
from demo_store import ADMIN_ID, CSRF_TOKEN, MEMBER_ID, DemoStore
from policy import DemoPasskeyHooks, DemoUserManagerHooks
from rooted_app import create_app as create_rooted_app

ROOT = Path(__file__).resolve().parents[1]


def _as_cookie(client: TestClient, user_id: str) -> None:
    response = client.post(f"/demo/as/{user_id}", follow_redirects=False)
    assert response.status_code == 303
    assert client.cookies.get(SESSION_COOKIE) == user_id


def _as_session(client: TestClient, user_id: str) -> None:
    response = client.post(f"/portal/demo/as/{user_id}", follow_redirects=False)
    assert response.status_code == 303


@pytest.mark.parametrize(
    ("factory", "login", "account", "users", "sign_in"),
    (
        (create_app, "/login", "/account", "/admin/users", _as_cookie),
        (
            create_rooted_app,
            "/portal/login",
            "/portal/account",
            "/portal/admin/users",
            _as_session,
        ),
    ),
    ids=("cookie-default-paths", "session-rooted-paths"),
)
def test_generic_install_serves_identity_surfaces_on_both_hosts(
    factory, login: str, account: str, users: str, sign_in
) -> None:
    client = TestClient(factory(DemoStore()))
    page = client.get(login)
    assert page.status_code == 200
    assert 'data-passkey-form="login"' in page.text

    guest_users = client.get(users, follow_redirects=False)
    assert guest_users.status_code == 303
    assert guest_users.headers["location"].endswith(login) or guest_users.headers[
        "location"
    ] == login

    sign_in(client, ADMIN_ID)
    admin_users = client.get(users)
    admin_account = client.get(account)
    assert admin_users.status_code == admin_account.status_code == 200
    assert "data-platform-identity-authenticated" in admin_users.text
    assert "data-platform-identity-authenticated" in admin_account.text

    sign_in(client, MEMBER_ID)
    denied = client.get(users)
    assert denied.status_code == 403
    assert "Admin access required" in denied.text


def test_hosts_do_not_copy_adapter_installers() -> None:
    forbidden = (
        "install_passkey_ui(",
        "install_usermanager_ui(",
        "PasskeyRouteHooks(",
        "UserManagerUiConfig(",
        "apply_platform_context(",
        "render_login",
        "render_register",
    )
    for name in ("app.py", "rooted_app.py"):
        source = (ROOT / name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        text = ast.unparse(tree)
        for marker in forbidden:
            assert marker not in text, f"{name} still copies {marker}"
        assert "install_identity_adapters(" in source


def test_second_install_is_idempotent_then_conflicts_on_real_adapters() -> None:
    demo = DemoStore()
    app = FastAPI()
    templates = Jinja2Templates(directory=str(ROOT / "templates"))
    config = PlatformConfig(
        paths=PlatformPaths(),
        enable_account=True,
        enable_admin_users=True,
    )

    def session_user_id(_request) -> str | None:
        return None

    binding = PasskeyBinding(
        service=demo.passkey_service,
        hooks=DemoPasskeyHooks(
            demo,
            session_user_id=session_user_id,
            login_user=lambda *_args: None,
            logout_user=lambda *_args: None,
        ),
        cookies=PasskeyCookies(secure=False),
        csrf_token=lambda _request: CSRF_TOKEN,
    )
    um = UserManagerBinding(
        hooks=DemoUserManagerHooks(
            demo, session_user_id=session_user_id, activation_page="/activate"
        ),
        csrf_protection=_StaticCsrf(),
        environment=templates.env,
    )
    first = install_identity_adapters(
        app,
        environments=[templates.env],
        config=config,
        passkey=binding,
        usermanager=um,
    )
    second = install_identity_adapters(
        app,
        environments=[templates.env],
        config=config,
        passkey=binding,
        usermanager=um,
    )
    assert first is second
    assert first.passkey_ui is not None
    assert first.usermanager_ui is not None

    other = FastAPI()
    install_identity_adapters(
        other, environments=[Environment(loader=DictLoader({}))], config=config
    )
    with pytest.raises(IdentityAdapterConflict):
        install_identity_adapters(
            other,
            environments=[Environment(loader=DictLoader({}))],
            config=config,
            passkey=binding,
        )


def test_admin_mutation_fails_closed_without_csrf(client_cookie: TestClient) -> None:
    _as_cookie(client_cookie, ADMIN_ID)
    response = client_cookie.post(
        "/admin/users/invite",
        data={"username": "zoe", "email": "zoe@example.invalid", "role": "member"},
        follow_redirects=False,
    )
    assert response.status_code in {400, 403, 422}


class _StaticCsrf:
    def token(self, _request) -> str:
        return CSRF_TOKEN

    def validate(self, _request, submitted_token: str) -> None:
        if submitted_token != CSRF_TOKEN:
            raise PermissionError("invalid csrf token")


@pytest.fixture()
def client_cookie() -> TestClient:
    return TestClient(create_app(DemoStore()))
