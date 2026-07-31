"""Local chrome storybook for app-factory.

Run from the repo root:

    uv sync --extra dev
    uv run uvicorn example.app:app --reload --port 8765

Open http://127.0.0.1:8765 — iterate templates/CSS/JS here instead of
re-applying the same change in every product host.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app_factory.platform import (
    MenuGroup,
    MenuItem,
    PlatformConfig,
    PlatformLocale,
    PlatformPaths,
    PlatformUser,
    build_platform_context,
    install_platform,
)

ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))

ICON_HOME = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true"><path d="M3 10.5 12 3l9 7.5"/>'
    '<path d="M5 10v10h14V10"/></svg>'
)
ICON_USER = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="4"/>'
    '<path d="M4 21c1.5-4 5-6 8-6s6.5 2 8 6"/></svg>'
)
ICON_LAYERS = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true"><path d="m12 2 9 5-9 5-9-5 9-5Z"/>'
    '<path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/></svg>'
)

SIGNED_IN = PlatformUser(display_name="Ada Lovelace", is_admin=True, user_id="ada")

CONFIG = PlatformConfig(
    app_name="app-factory",
    brand_href="/",
    brand_meta="storybook",
    menu=(
        MenuItem("Catalog", "/", key="catalog", icon=ICON_HOME),
        MenuGroup(
            "Shell states",
            (
                MenuItem("Guest product", "/stories/guest", key="guest", icon=ICON_USER),
                MenuItem(
                    "Signed-in product",
                    "/stories/signed-in",
                    key="signed-in",
                    icon=ICON_USER,
                ),
                MenuItem("Bare shell", "/stories/bare", key="bare", no_htmx=True),
                MenuItem("Account / logout", "/stories/account", key="account"),
            ),
        ),
        MenuGroup(
            "Behavior",
            (
                MenuItem(
                    "HTMX nav swap",
                    "/stories/htmx",
                    key="htmx",
                    icon=ICON_LAYERS,
                ),
                MenuItem(
                    "HTMX fragment B",
                    "/stories/htmx/b",
                    key="htmx-b",
                    icon=ICON_LAYERS,
                ),
                MenuItem("Locales", "/stories/locales", key="locales"),
                MenuItem("Components", "/stories/components", key="components"),
            ),
        ),
    ),
    paths=PlatformPaths(
        login="/stories/login",
        logout="/stories/logout",
        register="/stories/register",
        account="/stories/account",
        admin_users="/stories/admin-users",
    ),
    locales=(
        PlatformLocale("pl", "🇵🇱", href="/stories/locales?lang=pl"),
        PlatformLocale("en", "🇬🇧", href="/stories/locales?lang=en"),
        PlatformLocale("de", "🇩🇪", href="/stories/locales?lang=de"),
    ),
    default_locale="en",
    htmx_nav=True,
    enable_admin_users=True,
    show_register=True,
)

app = FastAPI(title="app-factory storybook", docs_url=None, redoc_url=None)
install_platform(app, environments=[TEMPLATES.env], config=CONFIG)

STORIES: tuple[dict[str, str], ...] = (
    {
        "href": "/stories/guest",
        "title": "Guest product shell",
        "blurb": "Sidebar login/register, no identity, theme toggle in header.",
    },
    {
        "href": "/stories/signed-in",
        "title": "Signed-in product shell",
        "blurb": "Account foot + avatar identity; no logout in chrome.",
    },
    {
        "href": "/stories/bare",
        "title": "Bare shell",
        "blurb": "Login-style frame: header theme only, no sidebar.",
    },
    {
        "href": "/stories/account",
        "title": "Account / session",
        "blurb": "platform_session partial — only surface for Log out.",
    },
    {
        "href": "/stories/htmx",
        "title": "HTMX navigation",
        "blurb": "Sidebar hx-get swaps #main-content; Alpine re-inits after swap.",
    },
    {
        "href": "/stories/locales",
        "title": "Locale picker",
        "blurb": "Flag dropdown when more than one locale is configured.",
    },
    {
        "href": "/stories/components",
        "title": "Presentation primitives",
        "blurb": "Basecoat + .app-* helpers shipped with the factory CSS.",
    },
    {
        "href": "/stories/login",
        "title": "Login stub",
        "blurb": "Placeholder for my-auth passkey surface (not wired here).",
    },
)


def _lang(request: Request) -> str:
    return request.query_params.get("lang") or CONFIG.default_locale or "en"


def _ctx(
    request: Request,
    *,
    user: PlatformUser | None = None,
    page_title: str = "",
    nav_active: str = "",
    locales: tuple[PlatformLocale, ...] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    platform = build_platform_context(
        CONFIG,
        user=user,
        current_path=request.url.path,
        locales=locales,
        locale=_lang(request),
    )
    return {
        "request": request,
        "stories": STORIES,
        "page_title": page_title,
        "nav_active": nav_active,
        "lang": _lang(request),
        **platform,
        **extra,
    }


def _render(
    request: Request,
    template_name: str,
    *,
    user: PlatformUser | None = None,
    page_title: str = "",
    nav_active: str = "",
    locales: tuple[PlatformLocale, ...] | None = None,
    **extra: Any,
) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        request,
        template_name,
        _ctx(
            request,
            user=user,
            page_title=page_title,
            nav_active=nav_active,
            locales=locales,
            **extra,
        ),
    )


@app.get("/", response_class=HTMLResponse)
def catalog(request: Request) -> HTMLResponse:
    return _render(
        request,
        "catalog.html",
        user=SIGNED_IN,
        page_title="Story catalog",
        nav_active="catalog",
    )


@app.get("/stories/guest", response_class=HTMLResponse)
def story_guest(request: Request) -> HTMLResponse:
    return _render(
        request,
        "stories/guest.html",
        page_title="Guest product shell",
        nav_active="guest",
    )


@app.get("/stories/signed-in", response_class=HTMLResponse)
def story_signed_in(request: Request) -> HTMLResponse:
    return _render(
        request,
        "stories/signed_in.html",
        user=SIGNED_IN,
        page_title="Signed-in product shell",
        nav_active="signed-in",
    )


@app.get("/stories/bare", response_class=HTMLResponse)
def story_bare(request: Request) -> HTMLResponse:
    return _render(
        request,
        "stories/bare.html",
        page_title="Bare shell",
        nav_active="bare",
    )


@app.get("/stories/account", response_class=HTMLResponse)
def story_account(request: Request) -> HTMLResponse:
    return _render(
        request,
        "stories/account.html",
        user=SIGNED_IN,
        page_title="Account",
        nav_active="account",
    )


@app.get("/stories/htmx", response_class=HTMLResponse)
def story_htmx_a(request: Request) -> HTMLResponse:
    return _render(
        request,
        "stories/htmx.html",
        user=SIGNED_IN,
        page_title="HTMX panel A",
        nav_active="htmx",
        panel="A",
        alpine_count=0,
    )


@app.get("/stories/htmx/b", response_class=HTMLResponse)
def story_htmx_b(request: Request) -> HTMLResponse:
    return _render(
        request,
        "stories/htmx.html",
        user=SIGNED_IN,
        page_title="HTMX panel B",
        nav_active="htmx-b",
        panel="B",
        alpine_count=0,
    )


@app.get("/stories/locales", response_class=HTMLResponse)
def story_locales(request: Request) -> HTMLResponse:
    return _render(
        request,
        "stories/locales.html",
        user=SIGNED_IN,
        page_title="Locales",
        nav_active="locales",
    )


@app.get("/stories/components", response_class=HTMLResponse)
def story_components(request: Request) -> HTMLResponse:
    return _render(
        request,
        "stories/components.html",
        user=SIGNED_IN,
        page_title="Components",
        nav_active="components",
    )


@app.get("/stories/login", response_class=HTMLResponse)
def story_login(request: Request) -> HTMLResponse:
    return _render(request, "stories/login.html", page_title="Login stub")


@app.get("/stories/register", response_class=HTMLResponse)
def story_register(request: Request) -> HTMLResponse:
    return _render(request, "stories/register.html", page_title="Register stub")


@app.post("/stories/logout")
def story_logout() -> RedirectResponse:
    return RedirectResponse(url="/stories/guest", status_code=303)


@app.post("/stories/demo-form")
def story_demo_form(message: str = Form(default="")) -> HTMLResponse:
    safe = (message or "").strip() or "(empty)"
    return HTMLResponse(
        f'<p class="text-sm" data-demo-form-result>Submitted: {safe}</p>'
    )


@app.get("/stories/admin-users", response_class=HTMLResponse)
def story_admin_users(request: Request) -> HTMLResponse:
    return _render(
        request,
        "stories/admin_users.html",
        user=SIGNED_IN,
        page_title="Admin users stub",
        nav_active="admin-users",
    )
