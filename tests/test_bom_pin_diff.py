"""Fail-closed pin-diff: host + BOM vs preferred COMPAT row (report only)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOM_PATH = REPO_ROOT / "bom" / "multi_user.toml"
COMPAT_PATH = REPO_ROOT / "COMPAT.md"
HOST_PYPROJECT = REPO_ROOT / "examples" / "multi_user_bom" / "pyproject.toml"

_PREFERRED_ROW = re.compile(
    r"^\|\s*\*\*(v[\d.]+)\*\*\s*\|\s*\*\*(v[\d.]+)\*\*\s*\|\s*\*\*(v[\d.]+)\*\*",
    re.MULTILINE,
)
APP_FACTORY_OVERRIDE = "app-factory[platform]"


def bom_pins(text: str) -> dict[str, str]:
    pins = tomllib.loads(text)["pins"]
    return {
        "app-factory": str(pins["app-factory"]),
        "my-auth": str(pins["my-auth"]),
        "my-usermanager": str(pins["my-usermanager"]),
    }


def preferred_compat_row(text: str) -> tuple[str, str, str]:
    match = _PREFERRED_ROW.search(text)
    if match is None:
        raise AssertionError("COMPAT.md has no preferred BOM row")
    return match.group(1), match.group(2), match.group(3)


def host_git_tags(text: str) -> dict[str, object]:
    project = tomllib.loads(text)
    sources = project["tool"]["uv"]["sources"]
    overrides = list(project["tool"]["uv"]["override-dependencies"])
    app_factory = dict(sources["app-factory"])
    return {
        "my-auth": sources["my-auth"]["tag"],
        "my-usermanager": sources["my-usermanager"]["tag"],
        "overrides": overrides,
        "app-factory-override": APP_FACTORY_OVERRIDE in overrides,
        "app-factory-source": app_factory,
    }


def pin_diffs(
    *,
    bom: dict[str, str],
    compat: tuple[str, str, str],
    host_auth: str,
    host_usermanager: str,
    overrides: list[str],
) -> list[str]:
    diffs: list[str] = []
    expected = (bom["app-factory"], bom["my-auth"], bom["my-usermanager"])
    if compat != expected:
        diffs.append(f"COMPAT preferred row {compat} != BOM {expected}")
    if host_auth != bom["my-auth"]:
        diffs.append(f"host my-auth {host_auth} != BOM {bom['my-auth']}")
    if host_usermanager != bom["my-usermanager"]:
        diffs.append(
            f"host my-usermanager {host_usermanager} != BOM {bom['my-usermanager']}"
        )
    if overrides != [APP_FACTORY_OVERRIDE]:
        diffs.append(
            f"host override-dependencies {overrides} != [{APP_FACTORY_OVERRIDE!r}]"
        )
    return diffs


def test_pin_diffs_reports_host_auth_drift() -> None:
    diffs = pin_diffs(
        bom={"app-factory": "v0.6.22", "my-auth": "v0.5.4", "my-usermanager": "v0.6.5"},
        compat=("v0.6.22", "v0.5.4", "v0.6.5"),
        host_auth="v0.6.19",
        host_usermanager="v0.6.5",
        overrides=["app-factory[platform]"],
    )
    assert diffs
    assert any("my-auth" in item and "v0.6.19" in item for item in diffs)


def test_pin_diffs_reports_compat_row_drift() -> None:
    diffs = pin_diffs(
        bom={"app-factory": "v0.6.22", "my-auth": "v0.5.4", "my-usermanager": "v0.6.5"},
        compat=("v0.6.16", "v0.4.8", "v0.5.31"),
        host_auth="v0.5.4",
        host_usermanager="v0.6.5",
        overrides=["app-factory[platform]"],
    )
    assert diffs
    assert any("COMPAT" in item for item in diffs)


def test_pin_diffs_reports_extra_auth_override() -> None:
    diffs = pin_diffs(
        bom={
            "app-factory": "v0.6.22",
            "my-auth": "v0.5.4",
            "my-usermanager": "v0.6.5",
        },
        compat=("v0.6.22", "v0.5.4", "v0.6.5"),
        host_auth="v0.5.4",
        host_usermanager="v0.6.5",
        overrides=["app-factory[platform]", "my-auth[fastapi-htmx]"],
    )
    assert diffs
    assert any("override-dependencies" in item for item in diffs)


def test_pin_diffs_empty_when_host_and_compat_match_bom() -> None:
    assert (
        pin_diffs(
            bom={
                "app-factory": "v0.6.22",
                "my-auth": "v0.5.4",
                "my-usermanager": "v0.6.5",
            },
            compat=("v0.6.22", "v0.5.4", "v0.6.5"),
            host_auth="v0.5.4",
            host_usermanager="v0.6.5",
            overrides=["app-factory[platform]"],
        )
        == []
    )


def test_checked_in_pins_match_preferred_compat_row() -> None:
    bom = bom_pins(BOM_PATH.read_text(encoding="utf-8"))
    compat = preferred_compat_row(COMPAT_PATH.read_text(encoding="utf-8"))
    host = host_git_tags(HOST_PYPROJECT.read_text(encoding="utf-8"))
    diffs = pin_diffs(
        bom=bom,
        compat=compat,
        host_auth=host["my-auth"],
        host_usermanager=host["my-usermanager"],
        overrides=host["overrides"],
    )
    assert diffs == [], diffs
    assert bom["app-factory"] == "v0.6.23"
    assert bom["my-auth"] == "v0.5.4"
    assert bom["my-usermanager"] == "v0.6.5"
    assert host["app-factory-override"] is True
    assert "tag" not in host["app-factory-source"]
