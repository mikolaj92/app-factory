"""Contract for the thin product bootstrap (no product storage)."""

from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app_factory import ProductAppConfig, create_product_app, template_response
from app_factory import install_product_host
from app_factory.platform import MenuItem, PlatformConfig, PlatformPaths, PlatformUser
from app_factory.product import route_paths


def test_one_composition_serves_shell_assets_health_and_protects_mutations(
    tmp_path: Path,
):
    (tmp_path / "home.html").write_text(
        '{% extends "app_factory/product_shell.html" %}'
        "{% block content %}<h1>Domain</h1>{% endblock %}"
    )
    router = APIRouter()

    @router.get("/")
    def home(request: Request):
        return template_response(
            request.app.state.app_factory_product.environment, request, "home.html"
        )

    @router.post("/work")
    def work():
        return {"domain": True}

    app = create_product_app(
        ProductAppConfig(
            platform=PlatformConfig(app_name="Product", menu=(MenuItem("Home", "/"),)),
            template_directory=tmp_path,
        ),
        routers=(router,),
    )
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "<h1>Domain</h1>" in page.text
        assert 'aria-current="page"' in page.text
        assert "window.appTheme" in page.text
        assert "/static/platform/basecoat-factory.min.css" in page.text
        assert (
            client.get("/static/platform/basecoat-factory.min.css").status_code == 200
        )
        assert client.get("/health").json() == {"status": "ok"}
        assert client.post("/work").status_code == 403
        assert (
            client.post("/work", headers={"Origin": "https://evil.test"}).status_code
            == 403
        )
        assert client.post("/work", headers={"Origin": "http://testserver"}).json() == {
            "domain": True
        }


def test_route_paths_flattens_lazy_includes_without_empty_compile():
    host = FastAPI()
    nested = APIRouter()
    nested.add_api_route("/work", lambda: {"ok": True})
    wrapper = APIRouter()
    wrapper.include_router(nested, prefix="/api")
    host.include_router(wrapper)
    paths = list(route_paths(host.routes))
    assert any(route.path == "/api/work" for route in paths)
    assert all(route.path for route in paths)

    class BrokenInclude:
        original_router = nested
        include_context = object()

    # Missing prefix must not crash conflict checks during install.
    assert list(route_paths([BrokenInclude()])) == []


def test_install_is_noop_for_same_inputs_and_rejects_changed_config_or_routers():
    app = FastAPI()
    config = ProductAppConfig()
    router = APIRouter()
    first = install_product_host(app, config, routers=(router,))
    before = (list(app.routes), list(app.user_middleware), dict(app.exception_handlers))
    assert install_product_host(app, replace(config), routers=[router]) is first
    assert before == (app.routes, app.user_middleware, app.exception_handlers)
    with pytest.raises(ValueError, match="product host already installed"):
        install_product_host(
            app, replace(config, health_path="/ready"), routers=(router,)
        )
    with pytest.raises(ValueError, match="product host already installed"):
        install_product_host(app, config, routers=(APIRouter(),))
    assert before == (app.routes, app.user_middleware, app.exception_handlers)


@pytest.mark.parametrize(
    "path", ["/health", "/static/platform", "/static/platform/file.css", "/{path:path}"]
)
def test_conflicting_host_routes_fail_without_mutation(path):
    app = FastAPI()
    app.add_api_route(path, lambda: {})
    before = (list(app.routes), list(app.user_middleware))
    with pytest.raises(ValueError, match="conflict"):
        install_product_host(app, ProductAppConfig())
    assert before == (app.routes, app.user_middleware)


def test_root_prefix_and_host_lifespan(tmp_path):
    events = []

    @asynccontextmanager
    async def lifespan(app):
        events.append("start")
        app.state.host_resource = "host-owned"
        yield
        events.append("stop")

    router = APIRouter()

    @router.get("/")
    def home(request: Request):
        return {
            "resource": request.app.state.host_resource,
            "login": request.state.app_factory_platform_context["login_url"],
        }

    config = ProductAppConfig(
        platform=PlatformConfig(paths=PlatformPaths(root="/portal")),
        template_directory=tmp_path,
    )
    app = create_product_app(config, routers=(router,), lifespan=lifespan)
    assert events == []
    with TestClient(app) as client:
        assert client.get("/portal/").json() == {
            "resource": "host-owned",
            "login": "/portal/login",
        }
        assert client.get("/portal/health").status_code == 200
        assert (
            client.get("/portal/static/platform/basecoat-factory.min.css").status_code
            == 200
        )
        assert app.state.app_factory_product.environment.globals["platform_asset_url"](
            "htmx"
        ).startswith("/portal/static/platform/")
    assert events == ["start", "stop"]


def test_standard_errors_keep_http_semantics_and_escape_htmx_detail():
    router = APIRouter()

    @router.get("/denied")
    def denied():
        raise HTTPException(403, "<script>bad</script>", headers={"X-Reason": "policy"})

    @router.get("/number/{value}")
    def number(value: int):
        return value

    @router.get("/broken")
    def broken():
        raise RuntimeError("secret database credentials")

    app = create_product_app(ProductAppConfig(), routers=(router,))
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/denied").json() == {"detail": "<script>bad</script>"}
        denied = client.get("/denied", headers={"HX-Request": "true"})
        assert denied.status_code == 403
        assert denied.headers["X-Reason"] == "policy"
        assert 'role="alert"' in denied.text
        assert "&lt;script&gt;" in denied.text and "<script>" not in denied.text
        assert client.get("/missing").status_code == 404
        assert client.get("/number/no").status_code == 422
        assert (
            'role="alert"'
            in client.get("/number/no", headers={"HX-Request": "true"}).text
        )
        for headers in ({}, {"HX-Request": "true"}):
            broken = client.get("/broken", headers=headers)
            assert broken.status_code == 500
            assert "secret" not in broken.text
            assert "Internal Server Error" in broken.text


def test_htmx_http_error_escapes_non_string_detail_and_keeps_headers():
    router = APIRouter()

    @router.get("/denied")
    def denied():
        raise HTTPException(403, {"msg": "<x>"}, headers={"WWW-Authenticate": "Bearer"})

    @router.get("/empty")
    def empty():
        raise HTTPException(400, None)

    app = create_product_app(ProductAppConfig(), routers=(router,))
    with TestClient(app) as client:
        denied = client.get("/denied", headers={"HX-Request": "true"})
        assert denied.status_code == 403
        assert denied.headers["WWW-Authenticate"] == "Bearer"
        assert "<x>" not in denied.text
        assert "&lt;x&gt;" in denied.text
        empty = client.get("/empty", headers={"HX-Request": "true"})
        assert empty.status_code == 400
        assert 'role="alert"' in empty.text


def test_request_callbacks_are_local_and_changed_bindings_conflict():
    def user(request):
        return (
            PlatformUser(request.headers["x-user"])
            if "x-user" in request.headers
            else None
        )

    def locales(request):
        return None, request.headers.get("x-lang", "en")

    router = APIRouter()

    @router.get("/context")
    def context(request: Request):
        ctx = request.state.app_factory_platform_context
        return {
            "user": getattr(ctx["platform_user"], "display_name", None),
            "locale": ctx["platform_locale"],
        }

    config = ProductAppConfig()
    app = create_product_app(
        config, routers=(router,), current_user=user, locales=locales
    )
    with TestClient(app) as client:
        assert client.get(
            "/context", headers={"x-user": "Ada", "x-lang": "pl"}
        ).json() == {"user": "Ada", "locale": "pl"}
        assert client.get("/context").json() == {"user": None, "locale": "en"}
    assert app.state.app_factory_product.environment.globals["platform_user"] is None
    with pytest.raises(ValueError, match="already installed"):
        install_product_host(
            app, config, routers=(router,), current_user=lambda r: None, locales=locales
        )


def test_identity_bindings_use_existing_composer_and_shared_environment(monkeypatch):
    from app_factory import PasskeyBinding, UserManagerBinding
    from app_factory.adapters import IdentityInstall
    from app_factory.platform import install_platform
    import app_factory.product as product

    calls = []

    # Optional packages own ceremony; exercise the factory/composer boundary.
    def compose(app, **kwargs):
        calls.append(kwargs)
        platform = install_platform(
            app, environments=kwargs["environments"], config=kwargs["config"]
        )
        return IdentityInstall(platform, passkey_ui=object(), usermanager_ui=object())

    monkeypatch.setattr(product, "install_identity_adapters", compose)
    passkey = PasskeyBinding(service=object(), hooks=object())
    um = UserManagerBinding(hooks=object(), csrf_protection=object())
    config = ProductAppConfig()
    app = create_product_app(config, passkey=passkey, usermanager=um)
    installed = app.state.app_factory_product
    assert calls[0]["passkey"] is passkey
    assert calls[0]["usermanager"].hooks is um.hooks
    assert calls[0]["usermanager"].csrf_protection is um.csrf_protection
    assert calls[0]["usermanager"].environment is installed.environment
    assert installed.identity.passkey_ui is not None
    assert (
        install_product_host(app, config, passkey=passkey, usermanager=um) is installed
    )
    assert len(calls) == 1
    with pytest.raises(ValueError, match="already installed"):
        install_product_host(
            app, config, passkey=replace(passkey, hooks=object()), usermanager=um
        )


def test_custom_exception_handlers_are_not_silently_replaced():
    from starlette.exceptions import HTTPException as StarletteHTTPException

    app = FastAPI()

    async def custom(request, exc):
        return None

    app.add_exception_handler(StarletteHTTPException, custom)
    before = list(app.routes)
    with pytest.raises(ValueError, match="conflict"):
        install_product_host(app, ProductAppConfig())
    assert app.routes == before


def test_invalid_identity_fails_before_installing_chrome():
    from app_factory import PasskeyBinding, UserManagerBinding

    for bindings in (
        {"passkey": PasskeyBinding(service=None, hooks=object())},
        {"usermanager": UserManagerBinding(hooks=object())},
    ):
        app = FastAPI()
        before = list(app.routes)
        with pytest.raises(ValueError):
            install_product_host(app, ProductAppConfig(), **bindings)
        assert app.routes == before


def test_product_csrf_configuration_is_explicit():
    router = APIRouter()
    router.add_api_route("/work", lambda: {"ok": True}, methods=["POST"])
    router.add_api_route("/hooks/event", lambda: {"ok": True}, methods=["POST"])
    app = create_product_app(
        ProductAppConfig(
            csrf_trusted_origins=("https://trusted.test",),
            csrf_exempt_prefixes=("/hooks/",),
        ),
        routers=(router,),
    )
    with TestClient(app) as client:
        assert (
            client.post("/work", headers={"Origin": "https://trusted.test"}).status_code
            == 200
        )
        assert client.post("/hooks/event").status_code == 200
        assert client.post("/work").status_code == 403


@pytest.mark.parametrize("health_path", ["/health", "/login"])
def test_domain_router_cannot_shadow_identity_route(monkeypatch, health_path):
    from app_factory import PasskeyBinding
    from app_factory.adapters import IdentityInstall
    from app_factory.platform import install_platform
    import app_factory.product as product

    def compose(app, **kwargs):
        platform = install_platform(app, environments=kwargs["environments"])
        app.add_api_route("/login", lambda: "identity")
        return IdentityInstall(platform)

    monkeypatch.setattr(product, "install_identity_adapters", compose)
    router = APIRouter()
    router.add_api_route("/login", lambda: "domain")
    with pytest.raises(ValueError, match="conflict"):
        create_product_app(
            ProductAppConfig(health_path=health_path),
            routers=(router,) if health_path == "/health" else (),
            passkey=PasskeyBinding(service=object(), hooks=object()),
        )


def test_real_identity_packages_with_host_stores(monkeypatch):
    pytest.importorskip("my_auth")
    pytest.importorskip("my_usermanager")
    from app_factory import PasskeyBinding, SessionCsrfProtection, UserManagerBinding
    from starlette.middleware.sessions import SessionMiddleware

    example = Path(__file__).parents[1] / "examples" / "multi_user_bom"
    monkeypatch.syspath_prepend(str(example))
    from demo_store import ADMIN_ID, DemoStore
    from policy import DemoPasskeyHooks, DemoUserManagerHooks

    demo = DemoStore()
    csrf = SessionCsrfProtection()
    config = ProductAppConfig(
        platform=PlatformConfig(
            paths=PlatformPaths(root="/portal"), enable_account=True
        )
    )
    app = create_product_app(
        config,
        passkey=PasskeyBinding(
            service=demo.passkey_service,
            hooks=DemoPasskeyHooks(
                demo,
                session_user_id=lambda r: r.session.get("user"),
                login_user=lambda response, request, user: None,
                logout_user=lambda response, request: None,
            ),
            csrf_token=csrf.token,
        ),
        usermanager=UserManagerBinding(
            hooks=DemoUserManagerHooks(
                demo,
                session_user_id=lambda r: ADMIN_ID,
                activation_page="/portal/activate",
                csrf_token=csrf.token,
            ),
            csrf_protection=csrf,
        ),
        current_user=lambda r: PlatformUser("Admin", is_admin=True),
    )
    app.add_middleware(SessionMiddleware, secret_key="test-only", https_only=False)
    with TestClient(app) as client:
        for path in ("/portal/login", "/portal/account", "/portal/admin/users"):
            response = client.get(path)
            assert response.status_code == 200, response.text
            assert "/portal/static/platform/basecoat-factory.min.css" in response.text
        assert client.get("/portal/health").json() == {"status": "ok"}
        assert client.post("/portal/admin/users/invite").status_code == 403
