"""Preferred COMPAT.md BOM row must match bom/multi_user.toml."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOM_PATH = REPO_ROOT / "bom" / "multi_user.toml"
COMPAT_PATH = REPO_ROOT / "COMPAT.md"

_PREFERRED_ROW = re.compile(
    r"^\|\s*\*\*(v[\d.]+)\*\*\s*\|\s*\*\*(v[\d.]+)\*\*\s*\|\s*\*\*(v[\d.]+)\*\*",
    re.MULTILINE,
)


def _bom_pins() -> dict[str, str]:
    return tomllib.loads(BOM_PATH.read_text(encoding="utf-8"))["pins"]


def _compat_text() -> str:
    return COMPAT_PATH.read_text(encoding="utf-8")


def _preferred_compat_row() -> tuple[str, str, str]:
    match = _PREFERRED_ROW.search(_compat_text())
    assert match is not None, "COMPAT.md has no preferred BOM row"
    return match.group(1), match.group(2), match.group(3)


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    rest = text[start + len(heading) :]
    nxt = rest.find("\n### ")
    return text[start : start + len(heading) + nxt] if nxt != -1 else text[start:]


def test_compat_preferred_row_matches_bom_pins() -> None:
    pins = _bom_pins()
    app_factory, auth, um = _preferred_compat_row()
    assert app_factory == pins["app-factory"] == "v0.6.23"
    assert auth == pins["my-auth"] == "v0.5.4"
    assert um == pins["my-usermanager"] == "v0.6.5"


def test_upgrade_order_targets_preferred_row_not_archive_ban() -> None:
    text = _compat_text()
    pins = _bom_pins()
    section = _section(text, "### Supported upgrade order")
    assert pins["app-factory"] in section
    assert pins["my-auth"] in section
    assert pins["my-usermanager"] in section
    assert "Do **not** mix my-auth `v0.5.x`" not in section
    assert "v0.4.8" not in section
    assert "v0.5.9" not in section
    assert "v0.6.13" not in section
    assert "install_identity_adapters" in section
    assert 'override-dependencies = ["app-factory[platform]"]' in section


def test_host_migration_adopts_preferred_row_not_archive_composer() -> None:
    text = _compat_text()
    pins = _bom_pins()
    preferred = f"{pins['app-factory']} / {pins['my-auth']} / {pins['my-usermanager']}"
    section = _section(text, "### Migration from host installer forks")
    assert preferred in section
    assert "v0.6.13 / v0.4.8 / v0.5.9" not in section
    assert "install_identity_adapters" in section
    assert "install_passkey_ui" in section
    assert 'override-dependencies = ["app-factory[platform]"]' in text
