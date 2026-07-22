# app-factory

Shared **frontend chrome** for FastAPI + Jinja2 + HTMX + Alpine apps that use
[basecoat-factory](https://github.com/mikolaj92/basecoat-factory) and
[my-auth](https://github.com/mikolaj92/my-auth) passkeys.

The goal is one place to pin CDN assets, shell CSS/JS, and Jinja head partials so
product apps do **not** re-implement Basecoat loading, SRI pins, HTMX credential
wiring, or theme FOUC guards.

**Tag:** `v0.1.0`

---

## Platform stack (what we use)

This package is the thin shared layer in a small platform. Together:

| Piece | Role | How consumers get it |
|-------|------|----------------------|
| **app-factory** (this repo) | CDN pin + Jinja includes for chrome | `git` tag `v0.1.0` via uv |
| **basecoat-factory** | Basecoat + utility safelist + **app-shell** layout classes (`.app-*`) | **jsDelivr** only (pinned in this package) |
| **my-auth** (`fastapi-htmx`) | Passkey auth + **default** login/register UI | `git` tag `v0.2.0`; UI chrome uses app-factory |
| **my-usermanager** | Identity, roles, grants, session principal helpers | `git` branch/tag (pin so it depends on my-auth@v0.2.0) |
| **FastAPI + Jinja2 + HTMX + Alpine** | Server-rendered app shell | App code; scripts/CSS from factory pins |

### Dependency rule

- **Libraries and apps:** install via **git tags / branches** (or published tags), **not** `path = "../..."`.
- **CSS/JS chrome:** load from **jsDelivr** with **SHA-384 integrity**, not vendored copies of Basecoat/HTMX/Alpine in each app.
- **Product-only** assets stay in the app (domain CSS, charts, maps, icons).

### What lives where

| Concern | Owner |
|---------|--------|
| Pinned basecoat-factory / htmx / alpine URLs + SRI | **app-factory** |
| Shared `<head>` includes, theme boot script | **app-factory** templates |
| Login / register HTML + passkey UI static | **my-auth** `create_passkey_ui_router` |
| Session principal, roles, grants after login | **my-usermanager** + app hooks |
| Domain routes, ORM, product CSS | **the app** |

Apps should not ship:

- local `app-shell.css` as the platform shell (shell classes come from basecoat-factory),
- vendored `basecoat.css` / `htmx` / `alpine` as the only chrome,
- a parallel hand-rolled full-page login that replaces package passkey UI,
- a private copy of the CDN pin list (re-export `app_factory.cdn` instead).

---

## What this package exports

| Module / path | Purpose |
|---------------|---------|
| `app_factory.cdn` | Core + optional CDN assets, `cdn_asset()`, SRI verify, `extend_manifest` / `install_manifest` |
| `app_factory.jinja` | `configure_jinja_env()` — registers `cdn_asset` / `cdn_assets` and factory template loader |
| `app_factory/templates/app_factory/head_assets.html` | Core CSS/JS tags + HTMX credentials + 401 → login redirect |
| `app_factory/templates/app_factory/theme_boot.html` | Early dark/light/auto FOUC guard (`window.appTheme`) |

**Not included:** domain models, product routes, auth ceremony logic, product CSS.

---

## Core CDN pins (`v0.1.0`)

All core assets are on **cdn.jsdelivr.net** with integrity digests.

| Name | Package / version | Kind |
|------|-------------------|------|
| `basecoat-css` | basecoat-factory **v0.2.0** min CSS | style |
| `basecoat-js-all` | basecoat-factory **v0.2.0** min JS | script (defer) |
| `htmx` | htmx.org **2.0.10** | script |
| `alpine` | alpinejs **3.15.12** | script (defer) |

Lookup:

```python
from app_factory import cdn_asset, CDN_ASSET_MANIFEST

css = cdn_asset("basecoat-css")
# css.url, css.integrity, css.crossorigin, css.defer, css.order
```

Importing `app_factory.cdn` never performs network I/O. Call `verify_cdn_asset` /
`verify_cdn_manifest` explicitly in release or deploy checks.

### Optional extras (catalog)

Not in the default manifest; resolve via `cdn_asset(name)` or install into the
process-wide list:

| Name | Notes |
|------|--------|
| `chartjs` | Chart.js 4.4.1 |
| `leaflet-css` / `leaflet-js` | Leaflet 1.9.4 |
| `sortablejs` | SortableJS 1.15.3 |

```python
from app_factory.cdn import extend_manifest, install_manifest, cdn_asset

# Optional: make extras part of CDN_ASSET_MANIFEST for this process
install_manifest(extend_manifest(["chartjs", "leaflet-css", "leaflet-js"]))

# Or one-off lookup without install
chart = cdn_asset("chartjs")
```

Product templates load extras **after** the factory head include.

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
app-factory = { git = "https://github.com/mikolaj92/app-factory.git", tag = "v0.1.0" }
my-auth = { git = "https://github.com/mikolaj92/my-auth.git", tag = "v0.2.0" }
my-usermanager = { git = "https://github.com/mikolaj92/my-usermanager.git", branch = "main" }

# One resolved URL when extras pull the same packages transitively
[tool.uv]
override-dependencies = [
  "my-auth @ git+https://github.com/mikolaj92/my-auth.git@v0.2.0",
  "app-factory @ git+https://github.com/mikolaj92/app-factory.git@v0.1.0",
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
# Globals: cdn_asset, cdn_assets
# Loader can resolve: app_factory/head_assets.html, app_factory/theme_boot.html
```

Thin re-export (optional, keeps import paths stable inside the app):

```python
# app/utils/cdn_assets.py
from app_factory.cdn import (
    CDN_ASSET_MANIFEST,
    CDNAsset,
    CDNVerificationError,
    cdn_asset,
    extend_manifest,
    install_manifest,
    verify_cdn_asset,
    verify_cdn_manifest,
)
```

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

  {# Core: basecoat-factory + htmx + alpine (SRI) #}
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

- Emits core CSS then core JS in pin order.
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

1. Depend on `app-factory@v0.1.0` + `my-auth[fastapi-htmx]@v0.2.0` via git tags.
2. `configure_jinja_env` on every Jinja environment that renders full pages.
3. Include `app_factory/head_assets.html` (and usually `theme_boot.html`) in the shell.
4. Mount `create_passkey_ui_router` + package static; delete dead local login HTML.
5. Keep only product CSS / product CDN extras in the app.
6. Use uv `override-dependencies` if transitive extras resolve conflicting git URLs.
7. Contract-test: core CSS URL contains `basecoat-factory`, `/login` returns package UI, no `static/**/app-shell.css` platform shell.

---

## API sketch

```text
cdn_asset(name) -> CDNAsset
CDN_ASSET_MANIFEST          # core 4-tuple (immutable records)
OPTIONAL_ASSETS             # catalog dict
extend_manifest([...])      # core + named extras or CDNAsset instances
install_manifest(manifest)  # replace process-wide approved set
verify_cdn_asset / verify_cdn_manifest
configure_jinja_env(env, include_factory_templates=True)
factory_template_dirs()
```

---

## Versioning

| app-factory | basecoat-factory (CDN) | Notes |
|-------------|------------------------|--------|
| **v0.1.0** | **v0.2.0** | Initial public pin + Jinja chrome |

Bumping basecoat-factory requires new digests in `app_factory/cdn.py`, a tag
bump, and consumers refreshing the app-factory pin.

---

## Development

```bash
uv sync --extra dev
uv run pytest
```

---

## Related

- [basecoat-factory](https://github.com/mikolaj92/basecoat-factory) — CSS/JS dist on jsDelivr  
- [my-auth](https://github.com/mikolaj92/my-auth) — passkeys + fastapi-htmx UI  
- [my-usermanager](https://github.com/mikolaj92/my-usermanager) — users, grants, session principal  
