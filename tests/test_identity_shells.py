"""Shared identity-lifecycle shell composition contracts."""

from __future__ import annotations

from jinja2 import ChoiceLoader, DictLoader, Environment, PackageLoader
from starlette.testclient import TestClient

from app_factory.platform import (
    CLIENT_SHELL,
    IDENTITY_AUTHENTICATED_SHELL,
    IDENTITY_DENIED,
    IDENTITY_DENIED_FRAGMENT,
    IDENTITY_PUBLIC_SHELL,
    IDENTITY_PUBLIC_STATE,
    PlatformConfig,
    PlatformPaths,
    PlatformUser,
    apply_platform_context,
    install_platform,
)
from example.app import app
from fastapi import FastAPI

client = TestClient(app)


def _factory_env(extra_templates: dict[str, str] | None = None) -> Environment:
    loaders: list[object] = []
    if extra_templates:
        loaders.append(DictLoader(extra_templates))
    loaders.append(PackageLoader("app_factory", "templates"))
    return Environment(loader=ChoiceLoader(loaders), autoescape=True)


def test_identity_template_constants_match_package_names() -> None:
    assert IDENTITY_PUBLIC_SHELL == "app_factory/identity_public_shell.html"
    assert IDENTITY_AUTHENTICATED_SHELL == "app_factory/identity_authenticated_shell.html"
    assert IDENTITY_PUBLIC_STATE == "app_factory/identity_public_state.html"
    assert IDENTITY_DENIED == "app_factory/identity_denied.html"
    assert IDENTITY_DENIED_FRAGMENT == "app_factory/identity_denied_fragment.html"
    assert CLIENT_SHELL == "app_factory/client_shell.html"


def test_identity_public_shell_composes_branded_no_sidebar_chrome() -> None:
    env = _factory_env(
        {
            "activation.html": (
                "{% extends 'app_factory/identity_public_shell.html' %}"
                "{% block identity_notice %}<p data-host-notice>Policy</p>{% endblock %}"
                "{% block identity_panel %}<h1>Activate</h1>{% endblock %}"
                "{% block identity_footer %}<p data-host-footer>Help</p>{% endblock %}"
            )
        }
    )
    html = env.get_template("activation.html").render(
        app_name="Demo",
        platform_brand_href="/home",
        platform_asset_url=lambda name: f"/static/platform/{name}",
        lang="pl",
    )

    assert 'lang="pl"' in html
    assert "app-identity-public" in html
    assert "data-platform-identity-public" in html
    assert "data-platform-identity-public-frame" in html
    assert "data-platform-identity-panel" in html
    assert "data-host-notice" in html
    assert "data-host-footer" in html
    assert "Activate" in html
    assert '<a class="app-main-header__brand" href="/home">' in html
    assert "data-platform-theme-locale" in html
    assert "/static/platform/basecoat-css" in html
    assert "/static/platform/htmx" in html
    assert 'id="sidebar"' not in html
    assert "data-platform-identity-navigation" not in html
    assert "data-platform-foot" not in html


def test_identity_authenticated_shell_reuses_product_chrome_and_identity_nav() -> None:
    app_api = FastAPI()
    env = _factory_env(
        {
            "credentials.html": (
                "{% extends 'app_factory/identity_authenticated_shell.html' %}"
                "{% block content %}<h1>Passkeys</h1>{% endblock %}"
            )
        }
    )
    config = PlatformConfig(
        enable_account=True,
        enable_credentials=True,
        enable_admin_users=True,
        enable_invite=True,
        paths=PlatformPaths(),
    )
    install_platform(app_api, environments=[env], config=config)
    apply_platform_context(
        env,
        config,
        user=PlatformUser("Alice", is_admin=True),
        current_path="/account/passkeys",
    )

    html = env.get_template("credentials.html").render(page_title="Credentials")
    assert "app-identity-authenticated" in html
    assert "data-platform-identity-authenticated" in html
    assert 'id="sidebar"' in html
    assert "data-platform-identity-navigation" in html
    assert 'href="/account/passkeys"' in html
    assert 'href="/admin/users"' in html
    assert "Passkeys" in html
    assert "data-platform-theme-locale" in html
    assert "data-sidebar-toggle" in html


def test_identity_public_state_accepts_host_copy_without_enumeration() -> None:
    env = _factory_env(
        {
            "state.html": "{% include 'app_factory/identity_public_state.html' %}"
        }
    )
    html = env.get_template("state.html").render(
        identity_public_state_title="Łącze niedostępne",
        identity_public_state_message="Ten link wygasł lub został już użyty.",
        identity_public_state_action_href="/login",
        identity_public_state_action_label="Kontynuuj",
    )
    assert "data-platform-identity-public-state" in html
    assert 'role="alert"' in html
    assert 'data-variant="destructive"' in html
    assert "Łącze niedostępne" in html
    assert "Ten link wygasł lub został już użyty." in html
    assert 'href="/login"' in html
    assert "Kontynuuj" in html
    assert "Link unavailable" not in html


def test_identity_denied_page_and_fragment_share_stable_markers() -> None:
    env = _factory_env()
    fragment = env.get_template(IDENTITY_DENIED_FRAGMENT).render(
        identity_denied_title="Brak dostępu",
        identity_denied_message="Host odmówił uprawnień administratora.",
    )
    assert "data-platform-identity-denied" in fragment
    assert 'role="alert"' in fragment
    assert 'aria-live="assertive"' in fragment
    assert "Brak dostępu" in fragment

    app_api = FastAPI()
    config = PlatformConfig(
        enable_account=True,
        enable_admin_users=True,
        paths=PlatformPaths(),
    )
    install_platform(app_api, environments=[env], config=config)
    apply_platform_context(
        env,
        config,
        user=PlatformUser("Member", is_admin=False),
        current_path="/admin/users",
    )
    page = env.get_template(IDENTITY_DENIED).render(
        identity_denied_title="Brak dostępu",
        identity_denied_message="Host odmówił uprawnień administratora.",
        identity_denied_action_href="/account",
        platform_asset_url=lambda name: f"/static/platform/{name}",
    )
    assert "data-platform-identity-denied-page" in page
    assert "data-platform-identity-denied" in page
    assert "data-platform-identity-authenticated" in page
    assert 'id="sidebar"' in page
    assert "data-platform-identity-navigation" in page
    assert "Users" not in page.split("data-platform-identity-navigation")[1][:800]
    assert 'href="/account"' in page


def test_storybook_public_shells_preserve_locale_theme_and_invalid_states() -> None:
    valid = client.get("/stories/activation?capability=example&lang=de")
    assert valid.status_code == 200
    assert "data-platform-identity-public" in valid.text
    assert 'lang="de"' in valid.text
    assert "data-platform-theme-locale" in valid.text
    assert "data-theme-toggle" in valid.text
    assert 'id="sidebar"' not in valid.text
    assert "data-platform-identity-ceremony=\"activation\"" in valid.text
    assert "data-platform-identity-host-notice" in valid.text

    invalid = client.get("/stories/activation?state=expired")
    assert invalid.status_code == 200
    assert "data-platform-identity-public-state" in invalid.text
    assert 'role="alert"' in invalid.text
    assert "Link unavailable" in invalid.text

    recovery = client.get("/stories/recovery?capability=example")
    assert recovery.status_code == 200
    assert "data-platform-identity-ceremony=\"recovery\"" in recovery.text

    recovery_invalid = client.get("/stories/recovery?state=invalid")
    assert "data-platform-identity-public-state" in recovery_invalid.text


def test_storybook_authenticated_shells_and_fragment_swap() -> None:
    credentials = client.get("/stories/credentials")
    assert credentials.status_code == 200
    assert "data-platform-identity-authenticated" in credentials.text
    assert "data-platform-identity-navigation" in credentials.text
    assert 'href="/stories/credentials"' in credentials.text
    assert 'id="sidebar"' in credentials.text
    assert "data-sidebar-toggle" in credentials.text

    users = client.get("/stories/admin-users")
    assert users.status_code == 200
    assert "data-platform-identity-ceremony=\"users\"" in users.text
    assert "data-platform-users-fragment" in users.text
    assert 'hx-get="/stories/users/fragment"' in users.text
    assert 'hx-target="#users-fragment"' in users.text

    fragment = client.get("/stories/users/fragment")
    assert fragment.status_code == 200
    assert "data-platform-users-fragment" in fragment.text
    assert 'id="sidebar"' not in fragment.text

    denied = client.get("/stories/denied")
    assert denied.status_code == 200
    assert "data-platform-identity-denied" in denied.text
    assert "data-platform-identity-authenticated" in denied.text
    assert "Access denied" in denied.text
    # Non-admin member must not receive admin identity links.
    nav = denied.text.split("data-platform-identity-navigation")
    if len(nav) > 1:
        assert 'href="/stories/admin-users"' not in nav[1][:1200]


def test_client_shell_is_slim_basecoat_document_without_htmx_alpine() -> None:
    env = _factory_env(
        {
            "tap.html": (
                "{% extends 'app_factory/client_shell.html' %}"
                "{% block content %}"
                "<h1>TAP</h1>"
                "{% include 'app_factory/platform_session.html' %}"
                "{% endblock %}"
            )
        }
    )
    config = PlatformConfig(paths=PlatformPaths())
    apply_platform_context(
        env,
        config,
        user=PlatformUser("Ada"),
        current_path="/",
    )
    html = env.get_template("tap.html").render(
        app_name="TAP",
        platform_brand_href="/home",
        platform_asset_url=lambda name: f"/static/platform/{name}",
        lang="pl",
    )

    assert 'lang="pl"' in html
    assert "app-client" in html
    assert "data-platform-client" in html
    assert "data-platform-controls" in html
    assert "data-platform-theme-locale" in html
    assert "data-platform-auth" in html
    assert "data-platform-session" in html
    assert '<a class="app-main-header__brand" href="/home">' in html
    assert "TAP" in html
    assert "/static/platform/basecoat-css" in html
    assert "/static/platform/basecoat-js-all" in html
    assert "/static/platform/htmx" not in html
    assert "/static/platform/alpine" not in html
    assert "htmx:configRequest" not in html
    assert "Alpine.initTree" not in html
    assert 'id="sidebar"' not in html
    assert "data-platform-identity-navigation" not in html
    assert "htmx-indicator" not in html


def test_storybook_account_management_points_at_platform_paths() -> None:
    response = client.get("/stories/account-management")
    assert response.status_code == 200
    assert "data-platform-identity-authenticated" in response.text
    for path in (
        "/stories/activation?capability=example",
        "/stories/recovery?capability=example",
        "/stories/credentials",
        "/stories/admin-users",
        "/stories/denied",
    ):
        assert f'href="{path}"' in response.text
