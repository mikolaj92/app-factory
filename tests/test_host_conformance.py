"""Thin product-host conformance: chrome, static, CSRF, errors, identity glue."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.routing import Mount

from app_factory import (
    ProductAppConfig,
    SameOriginCsrfMiddleware,
    create_product_app,
    get_platform_static_app,
)
from app_factory.conformance import (
    FORBIDDEN_IDENTITY_INSTALLERS,
    HostConformanceError,
    HostConformanceReport,
    assert_thin_host,
    check_thin_host,
    check_thin_host_sources,
)

ROOT = Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "examples" / "minimal_host"
BOM = ROOT / "examples" / "multi_user_bom"
CORE_ASSET = "basecoat-factory.min.css"


def _load_example(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_minimal():
    return _load_example(MINIMAL / "app.py", "minimal_host_conformance_app").app


def test_example_sources_have_no_chrome_forks_or_direct_installers() -> None:
    check_thin_host_sources(MINIMAL, identity=False)
    check_thin_host_sources(BOM, identity=True)
    assert 'extends "app_factory/product_shell.html"' in (
        MINIMAL / "templates" / "home.html"
    ).read_text()
    assert 'extends "app_factory/identity_authenticated_shell.html"' in (
        BOM / "templates" / "home.html"
    ).read_text()


def test_minimal_host_passes_thin_host_conformance() -> None:
    report = assert_thin_host(_load_minimal(), MINIMAL, identity=False)
    assert report.static_path == "/static/platform"
    assert report.health_path == "/health"
    assert report.origin_csrf is True
    assert report.htmx_errors is True


def test_identity_host_requires_shared_static_mount() -> None:
    app = FastAPI()
    with pytest.raises(HostConformanceError, match="static mount"):
        check_thin_host(app, BOM, identity=True, probe=False, health_path=None)
    app.mount(
        "/static/platform",
        get_platform_static_app(),
        name="app-factory-platform",
    )
    report = check_thin_host(
        app, BOM, identity=True, probe=False, health_path=None
    )
    assert report.static_path == "/static/platform"
    assert report.origin_csrf is False
    assert report.health_path is None


def test_identity_host_must_use_composer(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    with pytest.raises(HostConformanceError, match="install_identity_adapters"):
        check_thin_host_sources(tmp_path, identity=True)


def test_forked_chrome_and_direct_identity_installers_fail(tmp_path: Path) -> None:
    (tmp_path / "templates").mkdir()
    (tmp_path / "static").mkdir()
    (tmp_path / "templates" / "product_shell.html").write_text(
        "{% block content %}fork{% endblock %}\n"
    )
    (tmp_path / "static" / CORE_ASSET).write_text("copied\n")
    (tmp_path / "app.py").write_text(
        "from my_auth.fastapi_htmx import install_passkey_ui\n"
        "from my_usermanager.adapters.fastapi_htmx import install_usermanager_ui\n"
        "install_passkey_ui(None)\n"
        "install_usermanager_ui(None)\n"
    )
    with pytest.raises(HostConformanceError) as caught:
        check_thin_host(FastAPI(), tmp_path, identity=True, probe=False)
    text = str(caught.value)
    assert "product_shell" in text
    assert CORE_ASSET in text
    assert "install_passkey_ui" in text
    assert "install_usermanager_ui" in text
    assert "install_identity_adapters" in text


def test_missing_shared_static_mount_fails() -> None:
    with pytest.raises(HostConformanceError, match="static mount"):
        check_thin_host(FastAPI(), MINIMAL, identity=False, probe=False)


def test_chrome_host_without_origin_csrf_fails() -> None:
    app = FastAPI()
    app.mount(
        "/static/platform",
        get_platform_static_app(),
        name="app-factory-platform",
    )
    with pytest.raises(HostConformanceError, match="Origin CSRF"):
        check_thin_host(app, MINIMAL, identity=False, probe=False)


def test_chrome_host_without_htmx_error_handlers_fails() -> None:
    app = FastAPI()
    app.mount(
        "/static/platform",
        get_platform_static_app(),
        name="app-factory-platform",
    )
    app.add_middleware(SameOriginCsrfMiddleware)
    with pytest.raises(HostConformanceError, match="HTMX error"):
        check_thin_host(app, MINIMAL, identity=False, probe=False)


def test_csrf_and_htmx_error_boundaries_are_enforced() -> None:
    router = APIRouter()

    @router.post("/work")
    def work() -> dict[str, bool]:
        return {"ok": True}

    @router.get("/denied")
    def denied():
        raise HTTPException(403, "nope")

    app = create_product_app(
        ProductAppConfig(template_directory=MINIMAL / "templates"),
        routers=(router,),
    )
    report = check_thin_host(
        app,
        MINIMAL,
        identity=False,
        page_path=None,
        mutation_path="/work",
    )
    assert report.origin_csrf is True
    assert report.htmx_errors is True
    with TestClient(app) as client:
        blocked = client.post("/work", headers={"Origin": "https://evil.test"})
        assert blocked.status_code == 403
        fragment = client.post(
            "/work",
            headers={"Origin": "https://evil.test", "HX-Request": "true"},
        )
        assert fragment.status_code == 403
        assert 'role="alert"' in fragment.text
        denied = client.get("/denied", headers={"HX-Request": "true"})
        assert denied.status_code == 403
        assert 'role="alert"' in denied.text


def test_forbidden_installer_markers_are_stable() -> None:
    assert FORBIDDEN_IDENTITY_INSTALLERS == (
        "install_passkey_ui(",
        "install_usermanager_ui(",
    )
    report = HostConformanceReport(
        static_path="/static/platform",
        health_path="/health",
        origin_csrf=True,
        htmx_errors=True,
    )
    mounts = [route for route in _load_minimal().routes if isinstance(route, Mount)]
    assert any(route.path == report.static_path for route in mounts)
