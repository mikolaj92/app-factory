# app-factory

Shared **frontend chrome** for FastAPI + Jinja2 + HTMX + Alpine apps that use
[basecoat-factory](https://github.com/mikolaj92/basecoat-factory) and
[my-auth](https://github.com/mikolaj92/my-auth) passkeys.

The goal is one place to ship the resilient same-origin chrome, Jinja head
partials, and optional CDN pins so product apps do **not** re-implement
Basecoat/HTMX/Alpine loading, credential wiring, or theme FOUC guards.

**Tag:** `v0.3.0`

---

## Platform stack (what we use)

This package is the thin shared layer in a small platform. Together:

| Piece | Role | How consumers get it |
|-------|------|----------------------|
| **app-factory** (this repo) | Bundled chrome assets + Jinja includes | `git` tag `v0.3.0` via uv |
| **basecoat-factory** | Build source for Basecoat + utility safelist + **app-shell** classes (`.app-*`) | Bundled in app-factory |
| **my-auth** (`fastapi-htmx`) | Passkey auth + **default** login/register UI | `git` tag `v0.2.0`; UI chrome uses app-factory |
| **my-usermanager** | Identity, roles, grants, session principal helpers | `git` branch/tag (pin so it depends on my-auth@v0.2.0) |
| **FastAPI + Jinja2 + HTMX + Alpine** | Server-rendered app shell | App code; core scripts/CSS served by the app |

### Dependency rule

- **Libraries and apps:** install via **git tags / branches** (or published tags), **not** `path = "../..."`.
- **Core CSS/JS chrome:** serve the files bundled in app-factory from the same origin; do not copy them into each app.
- **Product-only** assets stay in the app (domain CSS, charts, maps, icons).

### What lives where

| Concern | Owner |
|---------|--------|
| Bundled basecoat-factory / htmx / alpine files + manifest | **app-factory** |
| Shared `<head>` includes, optional CDN pins, theme boot script | **app-factory** |
| Login / register HTML + passkey UI static | **my-auth** `create_passkey_ui_router` |
| Session principal, roles, grants after login | **my-usermanager** + app hooks |
| Domain routes, ORM, product CSS | **the app** |

Apps should not ship:

- local `app-shell.css` as the platform shell (shell classes come from basecoat-factory),
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
| `app_factory/templates/app_factory/head_assets.html` | Same-origin core CSS/JS tags + HTMX credentials + 401 → login redirect |
| `app_factory/templates/app_factory/theme_boot.html` | Early dark/light/auto FOUC guard (`window.appTheme`) |

**Not included:** domain models, product routes, auth ceremony logic, product CSS.

---

## Bundled core assets (`v0.3.0`)

The wheel ships all core files. `MANIFEST.json` pins filenames, versions, and
SHA-384 digests; the runtime verifies it on first access.

| Name | Package / version | Kind |
|------|-------------------|------|
| `basecoat-css` | basecoat-css **1.0.2**, built with the app shell safelist | style |
| `basecoat-js-all` | basecoat-css **1.0.2** | script |
| `htmx` | htmx.org **2.0.10** | script |
| `alpine` | alpinejs **3.15.12** | script |

```python
from app_factory import bundled_asset, list_bundled_assets, platform_asset_url

css = bundled_asset("basecoat-css")
url = platform_asset_url(css.name)  # /static/platform/basecoat-factory.min.css
```

Exact sources, licenses, and digests are stored under `app_factory/assets/`.
### Shared presentation primitives

The bundled stylesheet keeps product markup Basecoat-first and adds only a
small domain-blind layer where utilities alone do not express the behavior:

- `.app-page`, `.app-stack`, `.app-header`, `.app-cluster`, and `.app-card-grid`
  compose responsive pages around Basecoat components.
- `.app-table-wrap` gives wide Basecoat tables a mobile overflow boundary.
- `.app-dropzone` styles a native file-input label or another correctly
  keyboard-enabled file target; set `data-dragover="true"` during drag-over.
- `.app-progress` normalizes native `<progress>` elements without replacing
  their semantics.

Product-specific statuses, worker states, and document actions stay in product
HTML and use Basecoat variants or semantic `data-*` attributes, not shared CSS.
Importing app-factory never performs network I/O.

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
app-factory = { git = "https://github.com/mikolaj92/app-factory.git", tag = "v0.3.0" }
my-auth = { git = "https://github.com/mikolaj92/my-auth.git", tag = "v0.2.0" }
my-usermanager = { git = "https://github.com/mikolaj92/my-usermanager.git", branch = "main" }

# One resolved URL when extras pull the same packages transitively
[tool.uv]
override-dependencies = [
  "my-auth @ git+https://github.com/mikolaj92/my-auth.git@v0.2.0",
  "app-factory @ git+https://github.com/mikolaj92/app-factory.git@v0.2.0",
]
```

```bash
uv lock && uv sync
```

---

## Wire Jinja (every host app)

```python
from fastapi.templating import Jinja2Templates
from app_factory import configure_jinja_env

templates = Jinja2Templates(directory="templates")  # or app/templates
configure_jinja_env(templates.env)
# Globals: bundled_asset, bundled_assets, platform_asset_url, cdn_asset, cdn_assets
# Loader can resolve: app_factory/head_assets.html, app_factory/theme_boot.html
```

Mount the bundled assets at the same prefix used by `head_assets.html`:

```python
from app_factory import get_platform_static_app

app.mount(
    "/static/platform",
    get_platform_static_app(),
    name="app_factory_platform",
)
```

Use `{% set platform_assets_prefix = '/other-prefix' %}` before the head include
when mounting elsewhere.

---

## Wire templates (shared chrome)

Minimal host `base.html` pattern:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  {% include "app_factory/theme_boot.html" %}
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}App{% endblock %}</title>

  {# Same-origin core: basecoat-factory + htmx + alpine #}
  {% include "app_factory/head_assets.html" %}

  {# Product-only CSS (optional) #}
  <link rel="stylesheet" href="{{ static_asset_url('css/product.css') }}">

  {# Product-only CDN extras (optional) #}
  {% set chartjs = cdn_asset('chartjs') %}
  <script src="{{ chartjs.url }}" integrity="{{ chartjs.integrity }}" crossorigin="{{ chartjs.crossorigin }}"></script>
</head>
<body class="app-shell" data-theme="light">
  {% block body %}{% endblock %}
</body>
</html>
```

### `head_assets.html` behavior

- Emits URLs for the four bundled core files under `platform_assets_prefix`.
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

Shell layout classes (`.app-shell`, page chrome, etc.) come from
**basecoat-factory**, not from a per-app CSS fork.

---

## Passkey login (my-auth + this package)

Default interactive login/register should come from **my-auth**, not app templates.

```python
from my_auth.fastapi import PasskeyCookies, PasskeyRouteHooks
from my_auth.fastapi_htmx import PasskeyUiConfig, create_passkey_ui_router

# hooks: session user, registration policy, login → session principal, logout, …
ui = create_passkey_ui_router(
    service=passkey_service,
    hooks=hooks,
    config=PasskeyUiConfig(
        login_success_url="/",
        register_success_url="/",
        cookies=PasskeyCookies(secure=cookie_secure),
        # optional path overrides:
        # paths=PasskeyPaths(login_page="/login", …),
    ),
)
app.include_router(ui.router)
app.mount(ui.static_mount_path, ui.static_files, name="my_auth_fastapi_htmx_static")
```

- Package UI static defaults to `/auth/ui/static` (passkey-ui CSS/JS).
- my-auth’s `fastapi-htmx` extra depends on **app-factory** so package login pages
  use the same Basecoat chrome (`btn`, `card`, dark mode) as host shells.
- Domain recovery or one-off ceremony routes may stay app-owned; they must not
  replace the live login/register surface.

---

## Recommended app checklist

1. Depend on `app-factory@v0.3.0` + `my-auth[fastapi-htmx]@v0.2.0` via git tags.
2. Mount `get_platform_static_app()` at `/static/platform`.
3. `configure_jinja_env` on every Jinja environment that renders full pages.
4. Include `app_factory/head_assets.html` (and usually `theme_boot.html`) in the shell.
5. Mount `create_passkey_ui_router` + package static; delete dead local login HTML.
6. Keep only product CSS / product CDN extras in the app.
7. Contract-test that the local core assets and `/login` return 200.

---

## API sketch

```text
bundled_asset(name) -> BundledAsset
list_bundled_assets()
platform_asset_url(name, prefix="/static/platform")
get_platform_static_app()
cdn_asset(name) -> CDNAsset                 # optional extras only
extend_manifest / install_manifest
verify_cdn_asset / verify_cdn_manifest
configure_jinja_env(env, include_factory_templates=True)
factory_template_dirs()
```

---

## Versioning

| app-factory | basecoat-css | Notes |
|-------------|---------------|-------|
| **v0.2.0** | **1.0.2** | Bundled same-origin chrome; apps mount `/static/platform` |

Bump platform assets only through `uv run python scripts/refresh_platform_assets.py`.
The script uses the committed npm lockfile, rebuilds CSS, records licenses and
SHA-384 digests, and replaces `app_factory/assets/` after validation.

---

## Development

```bash
uv sync --extra dev
uv run pytest

# Regenerate bundled platform assets
uv run python scripts/refresh_platform_assets.py
```

---

## Related

- [basecoat-factory](https://github.com/mikolaj92/basecoat-factory) — CSS/JS dist on jsDelivr  
- [my-auth](https://github.com/mikolaj92/my-auth) — passkeys + fastapi-htmx UI  
- [my-usermanager](https://github.com/mikolaj92/my-usermanager) — users, grants, session principal  
