# app-factory

Shared **frontend chrome** for FastAPI + Jinja2 + HTMX + Alpine applications,
with locally bundled Basecoat UI assets and optional auth UI composition.

The goal is one place to ship the resilient same-origin chrome, Jinja head
partials, and optional CDN pins so product apps do **not** re-implement
Basecoat/HTMX/Alpine loading, credential wiring, or theme FOUC guards.

**Tag:** `v0.5.19`

---

## Platform stack (what we use)

This package is the thin shared layer in a small platform. Together:

| Piece | Role | How consumers get it |
|-------|------|----------------------|
| **app-factory** (this repo) | Bundled chrome, one FastAPI mount, and the shared Jinja shell | `git` tag `v0.5.19` via uv |
| **basecoat-factory** | Maintainer-only build source for the generated Basecoat/UI asset bundle | Not a runtime dependency |
| **my-auth** (`fastapi-htmx`) | Generic passkey login/register UI | Its compatible immutable tag |
| **my-usermanager** (`fastapi-htmx`) | Generic account/admin UI | Its compatible immutable tag |
| **FastAPI + Jinja2 + HTMX + Alpine** | Server-rendered app shell | App code; core scripts/CSS served by the app |

### Dependency rule

- **Libraries and apps:** install via **git tags / branches** (or published tags), **not** `path = "../..."`.
- **Core CSS/JS chrome:** serve the files bundled in app-factory from the same origin; do not copy them into each app.
- **Product-only** assets stay in the app (domain CSS, charts, maps, icons).

### What lives where

| Concern | Owner |
|---------|--------|
| Bundled Basecoat UI / HTMX / Alpine files + manifest | **app-factory** |
| Shared `<head>`, shell, optional CDN pins, and theme boot | **app-factory** |
| Login / register HTML + passkey UI static | **my-auth** `install_passkey_ui` |
| Generic account/admin HTML + UI static | **my-usermanager** `install_usermanager_ui` |
| Domain routes, ORM, product CSS | **the app** |

Apps should not ship:

- a local platform shell or runtime dependency on basecoat-factory,
- private copies of bundled `basecoat.css` / `htmx` / `alpine`,
- a parallel hand-rolled full-page login that replaces package passkey UI,
- a private copy of optional CDN pins (import `app_factory.cdn` instead).

---

## What this package exports

| Module / path | Purpose |
|---------------|---------|
| `app_factory.assets` | Verified bundled core assets, URL helper, and lazy Starlette static app |
| `app_factory.cdn` | Optional CDN assets, `cdn_asset()`, SRI verification, `extend_manifest()` / `install_manifest()` |
| `app_factory.jinja` | `configure_jinja_env()` — registers bundled/local and optional CDN helpers plus the template loader |
| `app_factory.fastapi` | `install_app_factory_ui()` — the sole supported FastAPI mount/Jinja integration |
| `app_factory/templates/app_factory/shell.html` | Shared five-block full-page shell |
| `app_factory/templates/app_factory/head_assets.html` | Same-origin core CSS/JS tags + HTMX credentials + 401 → login redirect |
| `app_factory/templates/app_factory/theme_boot.html` | Early dark/light/auto FOUC guard (`window.appTheme`) |
| `app_factory/templates/app_factory/shell_boot.html` | Shared shell JS (sidebar, active nav, basecoat, theme clicks) via `window.appShellConfig` |

**Not included:** domain models, product routes, auth ceremony logic, product CSS.

---

## Bundled core assets (`v0.5.19`)

The wheel ships all core files. `MANIFEST.json` pins filenames, versions, and
SHA-384 digests; the runtime verifies it on first access.

| Name | Package / version | Kind |
|------|-------------------|------|
| `basecoat-css` | basecoat-css **1.0.2**, built with the app shell safelist | style |
| `basecoat-js-all` | basecoat-css **1.0.2** | script |
| `htmx` | htmx.org **2.0.10** | script |
| `alpine` | alpinejs **3.15.12** | script |
| `material-symbols-css` | Material Symbols Outlined **v364** | style |
| `material-symbols-font` | Material Symbols Outlined **v364** | font |

```python
from app_factory import bundled_asset, list_bundled_assets, platform_asset_url

css = bundled_asset("basecoat-css")
url = platform_asset_url(css.name)  # /static/platform/basecoat-factory.min.css
```

Exact sources, licenses, and digests are stored under `app_factory/assets/`.
### Shared presentation contract (Basecoat-first, no npm in hosts)

Products link the factory CSS/JS bundle only. They do **not** install Tailwind
or Basecoat via npm. Layout and chrome come from this package; UI components
come from Basecoat inside the same bundle.

| Layer | Use | Examples |
|-------|-----|----------|
| **UI components** | Basecoat | `.card`, `.btn`, `.input`, `.field`, `.table` + `.table-container`, `.sidebar`, `.dialog`, … |
| **Layout primitives** | shipped `.app-*` (keep using these) | `.app-page`, `.app-stack` (+ `--tight`/`--sm`/`--compact`/`--section`), `.app-header`, `.app-cluster`, `.app-card-grid`, `.app-form__field` |
| **Shell chrome** | factory only | `.app-shell`, `.app-main*`, sidebar brand/foot glue, theme/locale |
| **Extra utilities** | safelist in factory build | `flex`, `grid`, `gap-*`, `md:grid-cols-*`, … — grow safelist when a host needs a new one |

Also shipped for product surfaces without inventing a second design system:

- `.app-table-wrap` — overflow boundary for wide tables (Basecoat `.table-container` is equivalent; either is fine)
- `.app-dropzone` — native file-input label / drag target (`data-dragover="true"`)
- `.app-progress` — native `<progress>` styling (Basecoat `.progress` is the div+span pattern)

Do **not** add new `.app-*` components for things Basecoat already has.
Product-specific statuses and actions stay in product HTML with Basecoat
variants or semantic `data-*` attributes. Importing app-factory never performs
network I/O.

### Optional CDN extras

Optional product integrations remain pinned on jsDelivr and are absent from
the default manifest:

| Name | Notes |
|------|--------|
| `chartjs` | Chart.js 4.4.1 |
| `leaflet-css` / `leaflet-js` | Leaflet 1.9.4 |
| `sortablejs` | SortableJS 1.15.3 |

```python
from app_factory.cdn import cdn_asset, extend_manifest, install_manifest

install_manifest(extend_manifest(["chartjs", "leaflet-css", "leaflet-js"]))
chart = cdn_asset("chartjs")
```

Call `verify_cdn_asset()` or `verify_cdn_manifest()` explicitly in release or
deploy checks. Product templates load extras after the factory head include.

---
## Install (git + uv)

Prefer a **tag**, not a local path:

```toml
# pyproject.toml
dependencies = [
  "app-factory",
  "my-auth[fastapi-htmx]",
  "my-usermanager[fastapi,myauth]",  # extras as needed
]

[tool.uv.sources]
app-factory = { git = "https://github.com/mikolaj92/app-factory.git", tag = "v0.5.19" }
my-auth = { git = "https://github.com/mikolaj92/my-auth.git", tag = "v0.3.23" }
my-usermanager = { git = "https://github.com/mikolaj92/my-usermanager.git", tag = "v0.4.5" }
```

```bash
uv lock && uv sync
```

---

## Install the platform once

```python
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from app_factory.fastapi import install_app_factory_ui

app = FastAPI()
templates = Jinja2Templates(directory="templates")
platform = install_app_factory_ui(app, environments=[templates.env])
```

This mounts the verified assets at `/static/platform`, installs the package
template loader, and binds `platform_asset_url(name)` to that mount. Repeating
the same installation configures newly supplied environments without adding a
second mount. A different path or mount name raises `AppFactoryUiConflict`.

Low-level asset/Jinja helpers remain available for non-application tooling, but
hosts use `install_app_factory_ui` rather than mounting or wiring them manually.

---

## Shared shell

Full-page templates extend the sole platform shell:

```html
{% extends "app_factory/shell.html" %}
{% block title %}Example{% endblock %}
{% block navigation %}<nav>Product navigation</nav>{% endblock %}
{% block main %}<h1>Ready</h1>{% endblock %}
```

The supported blocks include `title`, `head_extra`, `body` / `navigation` /
`header` / `content` / `page_scripts` / `loading_label` / `content_class` /
`body_end`, plus product-shell header slots `header_controls_start` /
`header_controls_end` / `sidebar_toggle_icon`. Signed-in identity and its
deterministic initial avatar render in the product header; the sidebar footer is
reserved for guest login/register. The shell loads theme boot,
platform assets, and `shell_boot`. Product CSS and domain behavior remain
host-owned.

### Product shell (logged-in chrome)

```html
{% extends "app_factory/product_shell.html" %}
{% block head_extra %}
  <script>window.appShellConfig = { /* optional */ };</script>
{% endblock %}
{% block content %}
  <h1>Queue</h1>
{% endblock %}
```

Host supplies **data** via `build_platform_context` / per-request context:
`platform_menu`, `platform_user`, `platform_paths`, locales. `PlatformUser`
derives a stable background and initial for its high-contrast fallback avatar.
Do not fork sidebar or main-header markup — inject extras only through blocks
(`header_controls_start` for notifications, `body_end` for toasts).

### `head_assets.html` behavior

- Emits URLs for the four bundled core files under the installer-bound prefix.
- Optional single product stylesheet via template variable:

  ```jinja
  {% set product_css_url = "/static/css/product.css" %}
  {% include "app_factory/head_assets.html" %}
  ```

- Configures HTMX to send cookies (`withCredentials`).
- On HTMX **401**, redirects to `login_url` if set, else `/login`:

  ```jinja
  {% set login_url = '/argus/login' %}  {# example: non-default path #}
  {% include "app_factory/head_assets.html" %}
  ```

### `theme_boot.html`

Runs before paint to set `document.documentElement` dark class from
`localStorage.themeMode` (`light` | `dark` | `auto`). Exposes `window.appTheme`
(`set` / `toggle` / `mode`). Host UIs may alias this for product naming.

### `shell_boot.html`

One shared IIFE for product/operator chrome behaviour previously copied into
each host `base.html`:

- sidebar toggle (`[data-sidebar-toggle]`, `basecoat:sidebar`, Escape)
- Basecoat `initAll` on load / HTMX swap / history cache
- active nav (`aria-current`, optional `.app-nav-link--active`)
- theme clicks (`[data-theme]`, `[data-theme-toggle]`) via `window.appTheme`

Configure **before** the include (or in `head_extra` when extending `shell.html`):

```html
<script>
  window.appShellConfig = {
    titleSuffix: 'Argus',              // optional document title suffix
    useDataNavActive: true,            // #main-content[data-nav-active] + [data-nav-key]
    activeNavAliases: { runs: 'queue' },
    reinitPageScripts: true,           // reload #main-content script[src] after swap
    syncToggleAria: true,              // keep toggle aria-expanded in sync
    activeLinkClass: false,            // disable class toggle (aria-current only)
  };
</script>
{% include "app_factory/shell_boot.html" %}
```

`shell.html` includes `shell_boot` after `head_extra`. Standalone host bases that
only include `head_assets` should also include `shell_boot` once and delete any
local copy of the sidebar/basecoat IIFE.

Shell layout classes (`.app-shell`, page chrome, etc.) are compiled into the
app-factory asset bundle; applications do not install the build-source project.

---

## Passkey login (my-auth + this package)

Default interactive login/register should come from **my-auth**, not app templates.

```python
from my_auth.fastapi import PasskeyCookies, PasskeyRouteHooks
from my_auth.fastapi_htmx import PasskeyUiConfig, install_passkey_ui

# Install the platform first, then give both auth adapters the same typed value.
passkeys = install_passkey_ui(
    app,
    platform=platform,
    service=passkey_service,
    hooks=hooks,
    config=PasskeyUiConfig(
        login_success_url="/",
        register_success_url="/",
        cookies=PasskeyCookies(secure=cookie_secure),
    ),
)

# Optional generic account/admin composition:
# users = install_usermanager_ui(
#     app, platform=platform, hooks=user_hooks, config=user_ui_config
# )
```

- The installer owns the package-specific static mount; hosts do not mount it manually.
- my-auth’s `fastapi-htmx` extra depends on **app-factory** so package login pages
  use the same Basecoat chrome (`btn`, `card`, dark mode) as host shells.
- Domain recovery or one-off ceremony routes may stay app-owned; they must not
  replace the live login/register surface.

---

## Recommended app checklist

1. Depend on `app-factory[platform]@v0.5.19` and auth tags from `COMPAT.md`.
2. Call `install_app_factory_ui()` once with every Jinja environment.
3. Extend `app_factory/shell.html`; keep navigation and domain UI in the host.
4. Pass the returned `AppFactoryUi` to auth/usermanager adapter installers.
5. Keep only product CSS and product CDN extras in the app.
6. Contract-test that canonical local assets and enabled UI routes return 200.

---

## API sketch

install_app_factory_ui(app, environments, static_path, mount_name) -> AppFactoryUi
bundled_asset(name) -> BundledAsset
list_bundled_assets()
platform_asset_url(name, prefix="/static/platform")
get_platform_static_app()                    # low-level
cdn_asset(name) -> CDNAsset                  # optional extras only
extend_manifest / install_manifest
verify_cdn_asset / verify_cdn_manifest
configure_jinja_env(env)                     # low-level
factory_template_dirs()

---

## Versioning

| app-factory | basecoat-css | Notes |
|-------------|---------------|-------|
| **v0.5.19** | **1.0.2** | Full Basecoat + HTMX + Alpine + app shell + Material Symbols Outlined v364; hard pytest no-npm contract |
| v0.5.17 | 1.0.2 | Basecoat-first contract docs + CSS keep-list |

Bump platform assets only through `uv run python scripts/refresh_platform_assets.py`.
The script uses the committed npm lockfile, rebuilds CSS, records licenses and
SHA-384 digests, and replaces `app_factory/assets/` after validation.

---

## Development

```bash
uv sync --extra dev
uv run pytest

# Local chrome storybook (LAN-visible; iterate shell/CSS/JS here)
uv run uvicorn example.app:app --host 0.0.0.0 --port 8765 --app-dir .
# open http://127.0.0.1:8765 or http://<lan-ip>:8765
# launchd unit: gui/$(id -u)/dev.app-factory.storybook

# Regenerate bundled platform assets
uv run python scripts/refresh_platform_assets.py
```

The `example/` package is a small FastAPI host that mounts the real product
shell and walks guest/signed-in/bare/account/HTMX/locale/component states.
Use it as the default place to visual-check chrome changes before tagging.
`pythonpath = ["."]` keeps `example.app` importable for pytest and uvicorn.

Optional browser isolation (issue #9) skips unless Playwright is installed:

```bash
uv sync --extra browser
uv run playwright install chromium
uv run pytest tests/test_browser_chrome.py
```

---

## Related

- [basecoat-factory](https://github.com/mikolaj92/basecoat-factory) — maintainer-only generated asset source  
- [my-auth](https://github.com/mikolaj92/my-auth) — passkeys + fastapi-htmx UI  
- [my-usermanager](https://github.com/mikolaj92/my-usermanager) — users, grants, session principal  
