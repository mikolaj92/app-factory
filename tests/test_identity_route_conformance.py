"""Identity routing is checked from installed routes, not guessed URLs."""

from types import SimpleNamespace

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse
from starlette.routing import Mount

from app_factory.conformance import HostConformanceError, check_thin_host

from app_factory.adapters import PasskeyBinding, install_identity_adapters
from app_factory.platform import PlatformConfig, PlatformPaths


@pytest.mark.parametrize(
    "host_path", ["/portal/sign-in", "/portal/{page}", "/portal/{rest:path}"]
)
def test_existing_host_cannot_shadow_configured_identity(monkeypatch, host_path):
    import app_factory.adapters.compose as compose

    def install(app, **kwargs):
        router = APIRouter()
        router.add_api_route("/portal/sign-in", lambda: "identity", methods=["GET"])
        app.include_router(router)
        return SimpleNamespace(environment=None, router=router)

    monkeypatch.setattr(compose, "install_passkey_adapter", install)
    app = FastAPI(root_path="/proxy")
    app.add_api_route(host_path, lambda: "host", methods=["GET"])
    with pytest.raises(ValueError, match="identity route.*shadow"):
        install_identity_adapters(
            app,
            environments=[],
            config=PlatformConfig(paths=PlatformPaths(root="/portal")),
            passkey=PasskeyBinding(
                service=object(), hooks=object(), ui_config=object()
            ),
        )
    assert not hasattr(app.state, "app_factory_identity")


def _compose(monkeypatch, app):
    import app_factory.adapters.compose as compose

    def install(app, **kwargs):
        router = APIRouter()
        router.add_api_route("/portal/sign-in", lambda: "identity", methods=["GET"])
        app.include_router(router)
        return SimpleNamespace(environment=None, router=router)

    monkeypatch.setattr(compose, "install_passkey_adapter", install)
    return install_identity_adapters(
        app,
        environments=[],
        passkey=PasskeyBinding(service=object(), hooks=object(), ui_config=object()),
    )


@pytest.mark.parametrize("mount_path", ["/", "/portal"])
def test_earlier_mount_shadows_identity(monkeypatch, mount_path):
    app = FastAPI()
    app.mount(mount_path, PlainTextResponse("host"))
    with pytest.raises(ValueError, match="identity route.*shadow"):
        _compose(monkeypatch, app)


def test_disjoint_methods_and_later_catchall_are_valid(monkeypatch):
    app = FastAPI(root_path="/proxy")
    app.add_api_route("/portal/{page}", lambda: "host", methods=["POST"])
    _compose(monkeypatch, app)
    app.add_api_route("/{rest:path}", lambda: "fallback")
    from app_factory.adapters.route_contract import check_identity_routes

    check_identity_routes(app.routes, app.state.app_factory_identity_routes)
    with TestClient(app) as client:
        assert client.get("/proxy/portal/sign-in").json() == "identity"
        assert client.post("/proxy/portal/sign-in").json() == "host"


def test_conformance_detects_shadow_inserted_after_composition(monkeypatch, tmp_path):
    app = FastAPI()
    _compose(monkeypatch, app)
    app.routes.insert(0, Mount("/", app=PlainTextResponse("host")))
    (tmp_path / "app.py").write_text("install_identity_adapters(app)\n")
    with pytest.raises(HostConformanceError, match="identity route.*shadow"):
        check_thin_host(app, tmp_path, identity=True, probe=False, health_path=None)
