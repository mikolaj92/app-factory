"""Identity starter stays a thin host: shared chrome, no installer forks."""

from __future__ import annotations

from pathlib import Path

from app import create_app
from app_factory.conformance import assert_thin_host
from rooted_app import create_app as create_rooted_app

ROOT = Path(__file__).resolve().parents[1]


def test_cookie_and_rooted_hosts_are_thin() -> None:
    cookie = assert_thin_host(
        create_app(), ROOT, identity=True, health_path=None
    )
    rooted = assert_thin_host(
        create_rooted_app(),
        ROOT,
        identity=True,
        page_path="/portal/",
        health_path=None,
    )
    assert cookie.static_path == rooted.static_path == "/static/platform"
    assert cookie.health_path is None
    assert rooted.health_path is None
