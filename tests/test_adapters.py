"""Identity adapter composition: paths, session glue, fail-closed, conflicts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from jinja2 import DictLoader, Environment
from starlette.testclient import TestClient

from app_factory.adapters import (
    IdentityAdapterConflict,
    PasskeyBinding,
    UserManagerBinding,
    attach_platform_page_context,
    install_identity_adapters,
    install_platform_request_context,
)
from app_factory.adapters.paths import rooted_adapter_path, usermanager_path_kwargs
from app_factory.platform import (
    PlatformConfig,
    PlatformPaths,
    PlatformUser,
    join_platform_root,
)


def test_usermanager_paths_follow_platform_root_and_invite_post() -> None:
    paths = PlatformPaths(root="/argus")
    kwargs = usermanager_path_kwargs(paths)
    assert kwargs["login_url"] == "/argus/login"
    assert kwargs["account_path"] == "/argus/account"
    assert kwargs["users_path"] == "/argus/admin/users"
    assert kwargs["invite_path"] == "/argus/admin/users/invite"
    assert kwargs["invite_path"] != paths.resolved().invite
    assert kwargs["logout_path"] == "/argus/logout"
    assert kwargs["profile_path"] == "/argus/account/profile"
    assert rooted_adapter_path(paths, "/api/auth/login/options") == (
        "/argus/api/auth/login/options"
    )
    assert join_platform_root("/argus", "/login") == "/argus/login"


def test_derived_page_context_is_skipped_when_host_supplies_one() -> None:
    class HostHooks:
        def page_context(self, request: Request) -> dict[str, str]:
            return {"page_title": request.url.path}

        def list_users(self) -> tuple[()]:
            return ()

    hooks = HostHooks()
    wrapped = attach_platform_page_context(
        hooks,
        config=PlatformConfig(),
        current_user=lambda _request: PlatformUser("Ada"),
    )
    assert wrapped is hooks


def test_derived_page_context_fills_platform_globals() -> None:
    class HostHooks:
        def list_users(self) -> tuple[()]:
            return ()

    wrapped = attach_platform_page_context(
        HostHooks(),
        config=PlatformConfig(app_name="Ops", paths=PlatformPaths(root="/app")),
        current_user=lambda _request: PlatformUser("Ada", is_admin=True, user_id="ada"),
    )
    request = Request(
        {"type": "http", "method": "GET", "path": "/app/account", "headers": []}
    )
    ctx = wrapped.page_context(request)
    assert ctx["app_name"] == "Ops"
    assert ctx["platform_user"].display_name == "Ada"
    assert ctx["login_url"] == "/app/login"
    assert wrapped.list_users() == ()


def test_platform_request_context_updates_environment_per_request() -> None:
    app = FastAPI()
    environment = Environment(loader=DictLoader({"x": "{{ platform_user }}"}))
    config = PlatformConfig(app_name="Ops")

    def current_user(request: Request) -> PlatformUser | None:
        name = request.headers.get("x-user")
        return PlatformUser(name) if name else None

    install_platform_request_context(
        app,
        config=config,
        environments=[environment],
        current_user=current_user,
    )

    @app.get("/ping")
    def ping() -> dict[str, str]:
        user = environment.globals.get("platform_user")
        return {"name": getattr(user, "display_name", "")}

    client = TestClient(app)
    guest = client.get("/ping")
    signed = client.get("/ping", headers={"x-user": "Ada"})
    assert guest.json() == {"name": ""}
    assert signed.json() == {"name": "Ada"}


def test_install_identity_adapters_is_idempotent_and_conflicts() -> None:
    app = FastAPI()
    environment = Environment(loader=DictLoader({}))
    config = PlatformConfig(app_name="One")
    first = install_identity_adapters(
        app, environments=[environment], config=config
    )
    second = install_identity_adapters(
        app, environments=[environment], config=config
    )
    assert first is second
    assert first.passkey_ui is None
    assert first.usermanager_ui is None

    with pytest.raises(IdentityAdapterConflict):
        install_identity_adapters(
            app,
            environments=[environment],
            config=PlatformConfig(app_name="Two"),
        )


def test_adapter_modules_pass_ruff() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            "ruff",
            "check",
            "app_factory/adapters",
            "tests/test_adapters.py",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_identity_install_fails_closed_without_passkey_pair_or_csrf() -> None:
    app = FastAPI()
    environment = Environment(loader=DictLoader({}))
    with pytest.raises(ValueError, match="both"):
        install_identity_adapters(
            app,
            environments=[environment],
            passkey=PasskeyBinding(service=object(), hooks=None),
        )
    with pytest.raises(ValueError, match="csrf_protection"):
        install_identity_adapters(
            app,
            environments=[environment],
            usermanager=UserManagerBinding(hooks=object()),
        )
