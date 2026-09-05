"""Contract tests for the published multi-user platform BOM."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOM_PATH = REPO_ROOT / "bom" / "multi_user.toml"
COMPAT_PATH = REPO_ROOT / "COMPAT.md"
EXAMPLE_ROOT = REPO_ROOT / "examples" / "multi_user_bom"


def _bom() -> dict:
    return tomllib.loads(BOM_PATH.read_text(encoding="utf-8"))


def test_bom_pins_are_immutable_tags() -> None:
    bom = _bom()
    pins = bom["pins"]
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pins == {
        "app-factory": f"v{project['project']['version']}",
        "my-auth": "v0.5.4",
        "my-usermanager": "v0.6.4",
    }
    for name, tag in pins.items():
        assert tag.startswith("v"), name
        assert "main" not in tag
    assert bom["resolution"]["require_single_app_factory"] is True
    assert bom["resolution"]["override_dependencies"] == [
        "app-factory[platform]",
    ]


def test_compat_documents_bom_matrix_upgrade_order_and_migration() -> None:
    text = COMPAT_PATH.read_text(encoding="utf-8")
    bom = _bom()
    assert f"| **{bom['pins']['app-factory']}** | **{bom['pins']['my-auth']}** | **{bom['pins']['my-usermanager']}** |" in text
    assert "| **v0.6.4** | **v0.4.1** | **v0.5.2** |" in text
    assert "Identity lifecycle capability matrix" in text
    assert "Supported upgrade order" in text
    assert "Migration from host-owned recovery" in text
    assert 'override-dependencies = ["app-factory[platform]"]' in text
    assert (
        'override-dependencies = ["app-factory[platform]", "my-auth[fastapi-htmx]"]'
        not in text
    )
    assert "ensure_sqlite_schema" in text
    assert "SQLiteEnrollmentCapabilityStore" in text
    assert "1. **app-factory**" in text
    assert "2. **my-auth**" in text
    assert "3. **my-usermanager**" in text
    assert "4. **Host**" in text
    required_capabilities = (
        "Bootstrap registration",
        "Invitation activation",
        "Account recovery",
        "Account credentials",
        "Admin user management",
        "Invite issuance",
    )
    for label in required_capabilities:
        assert label in text


def test_example_pyproject_matches_bom_and_forces_single_source() -> None:
    bom = _bom()
    example = tomllib.loads((EXAMPLE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    sources = example["tool"]["uv"]["sources"]
    assert sources["my-auth"]["tag"] == bom["pins"]["my-auth"]
    assert sources["my-usermanager"]["tag"] == bom["pins"]["my-usermanager"]
    assert example["tool"]["uv"]["override-dependencies"] == bom["resolution"][
        "override_dependencies"
    ]
    readme = (EXAMPLE_ROOT / "README.md").read_text(encoding="utf-8")
    for tag in bom["pins"].values():
        assert tag in readme
    assert not (EXAMPLE_ROOT / "templates" / "invite.html").exists()
    assert not (EXAMPLE_ROOT / "templates" / "my_auth_overrides").exists()
    host_python = "".join(
        (EXAMPLE_ROOT / name).read_text(encoding="utf-8")
        for name in ("app.py", "rooted_app.py", "policy.py", "demo_store.py")
    )
    assert "create_invitation_tables" not in host_python
    assert "SQLiteEnrollmentCapabilityStore" not in host_python
    assert "my_auth_overrides" not in host_python
    assert "install_identity_adapters" in host_python
    assert "install_passkey_ui(" not in host_python
    assert "my-auth[fastapi-htmx]" not in example["tool"]["uv"]["override-dependencies"]


def test_example_integration_suite_passes() -> None:
    completed = subprocess.run(
        ["uv", "run", "pytest", "-q"],
        cwd=EXAMPLE_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert re.search(r"\d+ passed", completed.stdout), completed.stdout
