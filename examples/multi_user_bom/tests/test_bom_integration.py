"""Integration checks for the multi-user platform BOM example."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app import SESSION_COOKIE, create_app
from demo_store import ADMIN_ID, MEMBER_ID, DemoStore

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
BOM_PATH = REPO_ROOT / "bom" / "multi_user.toml"


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(DemoStore()))


def _as(client: TestClient, user_id: str) -> None:
    response = client.post(f"/demo/as/{user_id}", follow_redirects=False)
    assert response.status_code == 303
    assert client.cookies.get(SESSION_COOKIE) == user_id


def test_bom_pins_align_with_example_pyproject() -> None:
    bom = tomllib.loads(BOM_PATH.read_text(encoding="utf-8"))
    example = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    sources = example["tool"]["uv"]["sources"]
    assert sources["my-auth"]["tag"] == bom["pins"]["my-auth"]
    assert sources["my-usermanager"]["tag"] == bom["pins"]["my-usermanager"]
    assert example["tool"]["uv"]["override-dependencies"] == [
        "app-factory[platform]",
    ]
    assert bom["pins"]["app-factory"] == "v0.6.7"


def test_uv_lock_selects_single_app_factory_source() -> None:
    lock = ROOT / "uv.lock"
    if not lock.is_file():
        completed = subprocess.run(
            ["uv", "lock"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
    text = lock.read_text(encoding="utf-8")
    package_blocks = re.findall(
        r'(?m)^\[\[package\]\]\nname = "app-factory"\nversion = "([^"]+)"\n'
        r"source = \{([^}]+)\}",
        text,
    )
    assert package_blocks == [("0.6.7", ' editable = "../../" ')] or package_blocks == [
        ("0.6.7", 'editable = "../../"')
    ] or (
        len(package_blocks) == 1
        and package_blocks[0][0] == "0.6.7"
        and "editable" in package_blocks[0][1]
    ), package_blocks
    # Nested adapter git tags for older app-factory must not appear as package sources.
    assert "git+https://github.com/mikolaj92/app-factory@v0.5." not in text
    assert re.search(r'name = "my-auth"\nversion = "0\.4\.5"', text)
    assert "tag=v0.4.5" in text
    assert re.search(r'name = "my-usermanager"\nversion = "0\.5\.6"', text)
    assert "tag=v0.5.6" in text
    assert "tag=v0.4.0" not in text
    assert "tag=v0.4.1" not in text
    assert "tag=v0.4.2" not in text
    assert "tag=v0.4.4" not in text
    assert "tag=v0.5.1" not in text
    assert "tag=v0.5.2" not in text
    assert "tag=v0.5.4" not in text
    assert "tag=v0.5.5" not in text
    assert not re.search(r'name = "my-auth"\nversion = "0\.5\.', text)
    assert 'name = "my-auth", extras = ["fastapi-htmx"]' not in text.split(
        "[manifest]", 1
    )[-1].split("[[package]]", 1)[0]


def test_seeded_users_have_distinct_credentials(client: TestClient) -> None:
    store: DemoStore = client.app.state.demo_store
    admin_creds = store.credentials_for(ADMIN_ID)
    member_creds = store.credentials_for(MEMBER_ID)
    assert len(admin_creds) == 2
    assert len(member_creds) == 1
    assert {c.user_id for c in admin_creds} == {ADMIN_ID}
    assert {c.user_id for c in member_creds} == {MEMBER_ID}

    home = client.get("/")
    assert home.status_code == 200
    assert 'data-credential-counts' in home.text
    assert "admin: 2" in home.text
    assert "member: 1" in home.text


def test_credentials_page_is_owner_scoped_on_identity_shell(client: TestClient) -> None:
    _as(client, ADMIN_ID)
    admin_page = client.get("/account/passkeys")
    assert admin_page.status_code == 200
    assert "data-platform-identity-authenticated" in admin_page.text
    assert "data-platform-identity-ceremony=\"credentials\"" in admin_page.text
    assert "Admin laptop" in admin_page.text
    assert "Admin phone" in admin_page.text
    assert "Member passkey" not in admin_page.text

    _as(client, MEMBER_ID)
    member_page = client.get("/account/passkeys")
    assert member_page.status_code == 200
    assert "Member passkey" in member_page.text
    assert "Admin laptop" not in member_page.text


def test_bootstrap_register_and_login_pages_render(client: TestClient) -> None:
    register = client.get("/register")
    login = client.get("/login")
    assert register.status_code == login.status_code == 200
    assert 'data-passkey-form="register"' in register.text
    assert 'data-passkey-form="login"' in login.text


def test_invitation_activation_and_recovery_use_identity_public_shell(
    client: TestClient,
) -> None:
    _as(client, ADMIN_ID)
    invite = client.post(
        "/admin/users/invite",
        data={
            "username": "casey",
            "email": "casey@example.invalid",
            "role": "member",
            "csrf": "demo-bom-csrf",
        },
        follow_redirects=False,
    )
    assert invite.status_code == 303
    location = urlparse(invite.headers["location"])
    assert location.path == "/admin/users"
    activation_url = parse_qs(location.query)["invitation_url"][0]
    assert activation_url.startswith("/activate?capability=")

    activation = client.get(activation_url)
    assert activation.status_code == 200
    assert "data-platform-identity-public" in activation.text
    assert 'data-platform-identity-ceremony="activation"' in activation.text
    assert 'data-registration-kind="invitation"' in activation.text

    recovery = client.post("/demo/recovery/member", follow_redirects=False)
    assert recovery.status_code == 303
    recovery_url = recovery.headers["X-Demo-Recovery-URL"]
    page = client.get(recovery_url)
    assert page.status_code == 200
    assert "data-platform-identity-public" in page.text
    assert 'data-platform-identity-ceremony="recovery"' in page.text
    assert 'data-registration-kind="recovery"' in page.text

    invalid = client.get("/activate")
    assert invalid.status_code == 200
    assert "data-platform-identity-public-state" in invalid.text


def test_admin_users_and_account_use_authenticated_identity_shell(
    client: TestClient,
) -> None:
    _as(client, ADMIN_ID)
    users = client.get("/admin/users")
    account = client.get("/account")
    assert users.status_code == account.status_code == 200
    assert "data-platform-identity-authenticated" in users.text
    assert "data-platform-identity-authenticated" in account.text
    assert "Ada Admin" in users.text or "admin" in users.text
    assert "Morgan Member" in users.text or "member" in users.text
    assert "data-platform-identity-navigation" in users.text
    assert "Invite user" in users.text


def test_invite_page_denied_for_member(client: TestClient) -> None:
    _as(client, MEMBER_ID)
    denied = client.get("/admin/users")
    assert denied.status_code == 403
    assert "Admin access required" in denied.text
