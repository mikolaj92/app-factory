"""Platform composition: context, shell foot, install path."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from jinja2 import ChoiceLoader, DictLoader, Environment, PackageLoader
from starlette.testclient import TestClient

from app_factory.platform import (
    FORBIDDEN_BASECOAT_CLASS_MARKERS,
    IDENTITY_ADMIN_SURFACES,
    IDENTITY_AUTHENTICATED_SURFACES,
    IDENTITY_PUBLIC_SURFACES,
    MenuGroup,
    MenuItem,
    PlatformConfig,
    PlatformLocale,
    PlatformPaths,
    PlatformUser,
    apply_platform_context,
    build_platform_context,
    install_platform,
    join_platform_root,
)


def _env_with_factory() -> Environment:
    return Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        "page.html": (
                            "{% extends 'app_factory/product_shell.html' %}"
                            "{% block content %}BODY{% endblock %}"
                        )
                    }
                ),
                PackageLoader("app_factory", "templates"),
            ]
        ),
        autoescape=True,
    )


def test_build_platform_context_guest_vs_user() -> None:
    config = PlatformConfig(
        app_name="Demo",
        menu=(MenuItem("Home", "/"), MenuItem("Queue", "/queue")),
        paths=PlatformPaths(
            login="/login",
            logout="/logout",
            register="/join",
            recovery="/recover-account",
            account="/account",
            activation="/activate-account",
            credentials="/account/passkeys",
            invite="/admin/users/invite",
        ),
        enable_admin_users=True,
    )
    guest = build_platform_context(config, current_path="/queue")
    assert guest["platform_user"] is None
    assert guest["login_url"] == "/login"
    paths = guest["platform_paths"]
    assert paths.register == "/join"
    assert paths.activation == "/activate-account"
    assert paths.recovery == "/recover-account"
    assert paths.credentials == "/account/passkeys"
    assert paths.invite == "/admin/users/invite"
    assert paths.register != paths.recovery
    assert paths.activation != paths.recovery
    assert guest["platform_menu"][1].active is True
    assert guest["platform_identity_menu"] == ()

    user = build_platform_context(
        config,
        user=PlatformUser(display_name="Ops", is_admin=True, user_id="u1"),
        current_path="/",
    )
    assert user["platform_user"].display_name == "Ops"
    assert user["platform_user"].is_admin is True
    assert user["platform_user"].avatar_initial == "O"
    assert user["platform_user"].avatar_background.startswith("#")
    assert user["platform_user"].avatar_foreground == "#ffffff"


def test_platform_paths_defaults_match_adapter_contract() -> None:
    paths = PlatformPaths()
    assert paths.login == "/login"
    assert paths.logout == "/logout"
    assert paths.register == "/register"
    assert paths.activation == "/activate"
    assert paths.recovery == "/recover"
    assert paths.account == "/account"
    assert paths.credentials == "/account/passkeys"
    assert paths.admin_users == "/admin/users"
    assert paths.invite == "/admin/users"
    assert set(paths.public_hrefs()) == set(IDENTITY_PUBLIC_SURFACES)
    assert set(paths.authenticated_hrefs()) == set(IDENTITY_AUTHENTICATED_SURFACES)
    assert set(paths.admin_hrefs()) == set(IDENTITY_ADMIN_SURFACES)
    assert "account" not in paths.public_hrefs()
    assert "invite" not in paths.authenticated_hrefs()


def test_platform_paths_root_prefixes_without_double_join() -> None:
    assert join_platform_root("/argus", "/login") == "/argus/login"
    assert join_platform_root("/argus/", "/login") == "/argus/login"
    assert join_platform_root("", "/login") == "/login"
    assert join_platform_root("/argus", "/argus/login") == "/argus/login"

    rooted = PlatformPaths(root="/argus").resolved()
    assert rooted.root == ""
    assert rooted.login == "/argus/login"
    assert rooted.activation == "/argus/activate"
    assert rooted.credentials == "/argus/account/passkeys"
    assert rooted.invite == "/argus/admin/users"

    ctx = build_platform_context(
        PlatformConfig(paths=PlatformPaths(root="/argus")),
        current_path="/argus/account/passkeys",
        user=PlatformUser("Ada", is_admin=True),
    )
    assert ctx["login_url"] == "/argus/login"
    assert ctx["platform_paths"].recovery == "/argus/recover"
    assert ctx["platform_path_root"] == "/argus"


def test_identity_navigation_is_enabled_and_authorized_by_host_config() -> None:
    config = PlatformConfig(
        htmx_nav=True,
        paths=PlatformPaths(root="/app"),
        enable_account=True,
        enable_credentials=True,
        enable_admin_users=True,
        enable_invite=True,
    )

    guest = build_platform_context(config)
    assert guest["platform_identity_menu"] == ()
    # Public chrome must not leak authenticated/admin targets.
    assert guest["platform_enable_account"] is True
    assert all(
        item.href.startswith("/app/") is False
        for item in guest["platform_identity_menu"]
    )

    member = build_platform_context(
        config,
        user=PlatformUser("Member"),
        current_path="/app/account/passkeys",
    )
    assert [item.label for item in member["platform_identity_menu"]] == [
        "Account",
        "Credentials",
    ]
    assert [item.href for item in member["platform_identity_menu"]] == [
        "/app/account",
        "/app/account/passkeys",
    ]
    assert member["platform_identity_menu"][1].active is True
    assert all(item.key != "users" for item in member["platform_identity_menu"])
    assert all(item.key != "invite" for item in member["platform_identity_menu"])

    admin = build_platform_context(
        config,
        user=PlatformUser("Admin", is_admin=True),
        current_path="/app/admin/users",
    )
    assert [item.href for item in admin["platform_identity_menu"]] == [
        "/app/account",
        "/app/account/passkeys",
        "/app/admin/users",
        "/app/admin/users",
    ]
    assert admin["platform_identity_menu"][2].active is True


def test_product_shell_renders_guest_and_user_sidebar_foot() -> None:
    app = FastAPI()
    environment = _env_with_factory()
    config = PlatformConfig(
        app_name="Demo",
        menu=(MenuItem("Home", "/"),),
        paths=PlatformPaths(),
    )
    install_platform(app, environments=[environment], config=config)

    guest_html = environment.get_template("page.html").render()
    assert "data-platform-foot" in guest_html
    assert "data-platform-auth" in guest_html
    assert "Login" in guest_html
    assert 'href="/login"' in guest_html
    assert 'href="/register"' in guest_html
    assert "Create account" in guest_html
    assert 'href="/recover"' not in guest_html
    assert 'href="/activate"' not in guest_html
    assert 'href="/admin/users"' not in guest_html
    assert "data-platform-identity-navigation" not in guest_html
    # Theme lives in header partial, not the sidebar foot (script still mentions the attr).
    foot_start = guest_html.find("data-platform-foot")
    assert foot_start != -1
    foot_chunk = guest_html[foot_start : foot_start + 1200]
    assert "data-theme-toggle" not in foot_chunk
    assert "data-platform-auth" in foot_chunk
    assert "btn-primary" not in guest_html
    assert 'data-variant="primary"' in guest_html
    assert "BODY" in guest_html
    assert 'id="app-main"' in guest_html
    assert 'id="main-content"' in guest_html
    assert 'id="sidebar"' in guest_html
    assert "data-sidebar-toggle" in guest_html
    assert "data-platform-theme-locale" in guest_html
    assert "app-main-header" in guest_html
    assert "/static/platform/basecoat-factory.min.css" in guest_html
    assert "data-platform-locales" not in guest_html

    apply_platform_context(
        environment,
        config,
        user=PlatformUser(display_name="Alice", is_admin=False),
    )
    user_html = environment.get_template("page.html").render()
    assert "Alice" in user_html
    assert user_html.count("data-platform-account-link") == 1
    assert 'href="/account"' in user_html
    assert 'class="platform-avatar"' in user_html
    assert ">A</span>" in user_html
    assert "--platform-avatar-bg: #" in user_html
    assert "--platform-avatar-fg: #ffffff" in user_html
    assert "data-platform-foot" in user_html
    sidebar_start = user_html.find('id="sidebar"')
    sidebar_end = user_html.find("</aside>", sidebar_start)
    sidebar_chunk = user_html[sidebar_start:sidebar_end]
    assert "data-platform-account-link" in sidebar_chunk
    assert "platform-avatar" in sidebar_chunk
    assert "Alice" in sidebar_chunk
    header_start = user_html.find("app-main-header__controls")
    header_end = user_html.find("</header>", header_start)
    header_chunk = user_html[header_start:header_end]
    assert "data-platform-account-link" not in header_chunk
    # Logout is not in chrome — only on the account page partial.
    assert "Log out" not in user_html
    assert "Logout" not in user_html
    assert "Login" not in user_html


def test_product_shell_renders_enabled_identity_navigation_slot() -> None:
    app = FastAPI()
    environment = _env_with_factory()
    config = PlatformConfig(
        enable_account=True,
        enable_credentials=True,
        enable_admin_users=True,
        enable_invite=True,
        paths=PlatformPaths(),
    )
    install_platform(app, environments=[environment], config=config)
    apply_platform_context(
        environment,
        config,
        user=PlatformUser("Alice", is_admin=True),
        current_path="/account",
    )

    html = environment.get_template("page.html").render()
    assert "data-platform-identity-navigation" in html
    assert 'href="/account"' in html
    assert 'href="/account/passkeys"' in html
    assert 'href="/admin/users"' in html
    assert html.count('href="/admin/users"') == 2
    assert "Credentials" in html
    assert "Invite" in html
    nav_start = html.find("data-platform-identity-navigation")
    nav_chunk = html[nav_start : nav_start + 1200]
    assert 'aria-current="page"' in nav_chunk


def test_landing_shell_renders_shared_frame_and_host_blocks() -> None:
    environment = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        "landing_host.html": (
                            "{% extends 'app_factory/landing.html' %}"
                            "{% block landing_brand %}Temida{% endblock %}"
                            "{% block landing_content %}"
                            "<article id='intro' data-landing-chapter>Story</article>"
                            "{% endblock %}"
                            "{% block landing_visual %}"
                            "<div class='host-visual'></div>"
                            "{% endblock %}"
                        )
                    }
                ),
                PackageLoader("app_factory", "templates"),
            ]
        ),
        autoescape=True,
    )
    html = environment.get_template("landing_host.html").render(
        app_href="/app",
        app_label="Open app",
        landing_chapters=({"id": "intro", "label": "Intro"},),
        platform_asset_url=lambda name: f"/static/platform/{name}",
    )

    assert 'class="app-shell app-landing"' in html
    assert 'data-landing-shortcut' in html
    assert 'href="/app"' in html
    assert "Open app" in html
    assert "Temida" in html
    assert 'href="#intro"' in html
    assert "data-landing-chapter-link" in html
    assert "data-landing-reveal" in html
    assert "host-visual" in html
    assert "/static/platform/landing-css" in html
    assert "/static/platform/landing-js" in html


def test_landing_assets_preserve_no_js_and_theme_contract() -> None:
    root = Path(__file__).resolve().parents[1] / "app_factory" / "assets"
    css = (root / "landing.css").read_text(encoding="utf-8")
    script = (root / "landing.js").read_text(encoding="utf-8")

    assert 'html[data-theme="light"]' in css
    assert 'html[data-theme="dark"]' in css
    assert "html.is-enhanced:not(.is-reduced-motion)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "root.classList.add('is-enhanced')" in script
    assert "is-reduced-motion" in script
    assert "IntersectionObserver" in script

def test_factory_light_theme_uses_warm_paper_tokens() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "platform_assets_src"
        / "src"
        / "input.css"
    ).read_text(encoding="utf-8")
    bundled = (
        Path(__file__).resolve().parents[1]
        / "app_factory"
        / "assets"
        / "basecoat-factory.min.css"
    ).read_text(encoding="utf-8")

    assert 'html[data-theme="light"]' in source
    assert "--background: oklch(0.96 0.018 88)" in source
    assert "--card: oklch(0.985 0.012 88)" in source
    assert "--sidebar: oklch(0.935 0.022 86)" in source
    assert "--background:oklch(96% .018 88)" in bundled
    warm_block_start = source.index('html[data-theme="light"] {')
    warm_block = source[warm_block_start : source.index("}", warm_block_start)]
    assert ":root" not in warm_block
    assert ':root,\nhtml[data-theme="light"]' not in source
    assert "html[data-theme=light]" in bundled
    assert ".dark{" in bundled
    dark_start = bundled.index(".dark{")
    light_start = bundled.index("html[data-theme=light]")
    assert dark_start < light_start


def test_platform_theme_locale_partial() -> None:
    environment = _env_with_factory()
    environment.loader.loaders[0].mapping["header.html"] = (
        "{% include 'app_factory/platform_theme_locale.html' %}"
    )
    # ChoiceLoader uses DictLoader first — rebuild env with partial
    from jinja2 import ChoiceLoader, DictLoader, Environment, PackageLoader

    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        "header.html": (
                            "{% include 'app_factory/platform_theme_locale.html' %}"
                        )
                    }
                ),
                PackageLoader("app_factory", "templates"),
            ]
        ),
        autoescape=True,
    )
    apply_platform_context(
        env,
        PlatformConfig(paths=PlatformPaths()),
        locales=(
            PlatformLocale(code="pl", label="PL", href="/?lang=pl"),
            PlatformLocale(code="en", label="EN", href="/?lang=en"),
        ),
        locale="pl",
    )
    html = env.get_template("header.html").render()
    assert "data-platform-theme-locale" in html
    assert "data-theme-toggle" in html
    assert "theme-toggle-icon--light" in html
    assert "themeApi()?.toggle?.()" not in html  # theme_boot owns the click
    assert 'data-side="bottom"' in html
    assert 'data-align="end"' in html
    assert "data-platform-locale-picker" in html
    assert "data-platform-locales" in html
    assert 'data-href="/?lang=pl"' in html
    assert "data-platform-locale-select" not in html
    # Single dropdown, not a row of language buttons.
    assert html.count("<select") == 1
    assert html.count("<option") >= 2

    apply_platform_context(
        env,
        PlatformConfig(paths=PlatformPaths()),
        locales=(
            PlatformLocale(code="pl", label="PL"),
            PlatformLocale(code="en", label="EN"),
        ),
        locale="en",
    )
    client_html = env.get_template("header.html").render()
    assert "data-platform-locale-picker" in client_html
    assert "data-href=" not in client_html


def test_platform_hides_single_locale_picker() -> None:
    from jinja2 import ChoiceLoader, DictLoader, Environment, PackageLoader

    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        "header.html": (
                            "{% include 'app_factory/platform_theme_locale.html' %}"
                        )
                    }
                ),
                PackageLoader("app_factory", "templates"),
            ]
        ),
        autoescape=True,
    )
    apply_platform_context(
        env,
        PlatformConfig(paths=PlatformPaths()),
        locales=(PlatformLocale(code="pl", label="PL"),),
        locale="pl",
    )

    html = env.get_template("header.html").render()
    assert "data-platform-locale-picker" not in html
    assert "data-theme-toggle" in html


def test_theme_boot_uses_server_theme_and_syncs_html_attribute() -> None:
    environment = _env_with_factory()
    html = environment.get_template("app_factory/theme_boot.html").render()
    assert "document.documentElement.dataset.theme" in html
    assert "validModes.has(serverMode) ? serverMode : 'auto'" in html
    assert "dataset.theme = isDark() ? 'dark' : 'light'" in html
    assert "event.target.closest?.('[data-theme-toggle], button[data-theme], [role=\"button\"][data-theme]')" in html
    assert "window.appTheme.toggle()" in html
    assert "closest?.('[data-theme], [data-theme-toggle]')" not in html


def test_head_assets_reinit_alpine_after_htmx_swap() -> None:
    environment = _env_with_factory()
    html = environment.get_template("app_factory/head_assets.html").render(
        platform_asset_url=lambda name: f"/static/platform/{name}"
    )
    assert "htmx:afterSwap" in html
    assert "Alpine.initTree" in html


def test_grouped_menu_and_htmx_nav_in_sidebar() -> None:
    app = FastAPI()
    environment = _env_with_factory()
    config = PlatformConfig(
        app_name="Ops",
        brand_href="/argus",
        htmx_nav=True,
        menu=(
            MenuGroup(
                "Product",
                (
                    MenuItem("Queue", "/queue", key="queue", use_htmx=True),
                    MenuItem("Docs", "/docs", use_htmx=True),
                ),
            ),
            MenuGroup(
                "Admin",
                (MenuItem("Users", "/admin/users", no_htmx=True),),
            ),
        ),
        paths=PlatformPaths(),
    )
    install_platform(app, environments=[environment], config=config)
    apply_platform_context(environment, config, current_path="/queue")
    html = environment.get_template("page.html").render()
    assert 'id="platform-group-1"' in html or "platform-group-1" in html
    assert "Product" in html and "Admin" in html
    assert 'hx-get="/queue"' in html
    assert 'hx-target="#main-content"' in html
    assert 'data-nav-key="queue"' in html
    assert 'aria-current="page"' in html
    # no_htmx admin link
    assert 'href="/admin/users"' in html
    assert 'hx-get="/admin/users"' not in html


def test_platform_session_partial_is_logout_surface() -> None:
    from jinja2 import ChoiceLoader, DictLoader, Environment, PackageLoader

    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        "account.html": (
                            "{% include 'app_factory/platform_session.html' %}"
                        )
                    }
                ),
                PackageLoader("app_factory", "templates"),
            ]
        ),
        autoescape=True,
    )
    apply_platform_context(env, PlatformConfig(paths=PlatformPaths()))
    html = env.get_template("account.html").render()
    assert "data-platform-session" in html
    assert "Log out" in html
    assert 'action="/logout"' in html
    assert 'data-variant="destructive"' in html
    assert "<footer>" in html
    assert html.index("<footer>") < html.index("<form") < html.index("</footer>")


def test_platform_session_partial_accepts_host_labels() -> None:
    from jinja2 import ChoiceLoader, DictLoader, Environment, PackageLoader

    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        "account.html": (
                            "{% include 'app_factory/platform_session.html' %}"
                        )
                    }
                ),
                PackageLoader("app_factory", "templates"),
            ]
        ),
        autoescape=True,
    )
    apply_platform_context(env, PlatformConfig(paths=PlatformPaths()))
    html = env.get_template("account.html").render(
        platform_session_title="Sesja",
        platform_session_description="Wyloguj się na tym urządzeniu.",
        platform_logout_label="Wyloguj",
    )
    assert "Sesja" in html
    assert "Wyloguj się na tym urządzeniu." in html
    assert "Wyloguj" in html
    assert "Log out" not in html



def test_install_platform_mounts_chrome_and_registers_state() -> None:
    app = FastAPI()
    environment = _env_with_factory()
    result = install_platform(
        app,
        environments=[environment],
        config=PlatformConfig(app_name="X"),
    )
    assert result.ui.static_path == "/static/platform"
    assert result.passkey_ui is None
    assert app.state.app_factory_platform is result

    client = TestClient(app)
    # Bundled CSS is mounted under platform static
    css = client.get("/static/platform/basecoat-factory.min.css")
    assert css.status_code == 200
    assert len(css.content) > 100


def test_platform_templates_forbid_pre_basecoat_class_names() -> None:
    root = Path(__file__).resolve().parents[1] / "app_factory" / "templates"
    offenders: list[str] = []
    for path in root.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        # strip jinja comments
        body = "\n".join(
            line for line in text.splitlines() if not line.strip().startswith("{#")
        )
        for marker in FORBIDDEN_BASECOAT_CLASS_MARKERS:
            if marker in body:
                offenders.append(f"{path.name}:{marker}")
    assert offenders == []


def test_shell_boot_template_exports_config_contract() -> None:
    """shell_boot is the shared residual host JS; config keys stay stable."""
    env = Environment(loader=PackageLoader("app_factory", "templates"), autoescape=True)
    html = env.get_template("app_factory/shell_boot.html").render()
    assert "window.appShellConfig" in html
    assert "window.__appShellBooted" in html
    assert "getSidebar" in html
    assert "initBasecoat" in html
    assert "data-sidebar-toggle" in html
    assert "htmx:afterSwap" in html
    assert "htmx:historyCacheHit" in html
    assert "basecoat:sidebar" in html
    assert "app-nav-link--active" in html
    assert "reinitPageScripts" in html
    assert "useDataNavActive" in html


def test_shell_includes_shell_boot_after_head_extra() -> None:
    env = Environment(loader=PackageLoader("app_factory", "templates"), autoescape=True)
    html = env.get_template("app_factory/shell.html").render(
        platform_asset_url=lambda name: f"/static/platform/{name}"
    )
    assert "window.__appShellBooted" in html
    assert html.index("htmx:configRequest") < html.index("window.__appShellBooted")


def test_bare_shell_header_links_brand_home() -> None:
    env = Environment(loader=PackageLoader("app_factory", "templates"), autoescape=True)
    html = env.get_template("app_factory/shell.html").render(
        app_name="Demo",
        platform_brand_href="/home",
        platform_asset_url=lambda name: f"/static/platform/{name}",
    )
    assert '<a class="app-main-header__brand" href="/home">' in html
    assert "Demo" in html


def test_product_shell_is_full_operator_frame() -> None:
    app = FastAPI()
    env = _env_with_factory()
    config = PlatformConfig(
        app_name="Demo",
        brand_href="/home",
        htmx_nav=True,
        default_hx_swap="innerHTML",
        default_hx_select=None,
        menu=(
            MenuGroup(
                "Main",
                items=(MenuItem("Home", "/home", icon="<i>h</i>"),),
            ),
        ),
        paths=PlatformPaths(),
    )
    install_platform(app, environments=[env], config=config)
    apply_platform_context(env, config, current_path="/home")
    html = env.get_template("page.html").render(page_title="Home")
    assert 'id="app-main"' in html
    assert 'id="main-content"' in html
    assert 'data-page-title="Home"' in html
    assert "app-main-header" in html
    assert "data-platform-theme-locale" in html
    assert "data-platform-foot" in html
    assert 'hx-get="/home"' in html
    assert 'hx-swap="innerHTML"' in html
    # default_hx_select=None → no hx-select on nav items
    nav_chunk = html.split('hx-get="/home"')[1][:240]
    assert "hx-select=" not in nav_chunk
    assert 'href="/home"' in html
