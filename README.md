# app-factory

Shared **frontend chrome** for FastAPI + Jinja2 + HTMX + Alpine applications,
with locally bundled Basecoat UI assets and optional auth UI composition.

The goal is one place to ship the resilient same-origin chrome, Jinja head
partials, and optional CDN pins so product apps do **not** re-implement
Basecoat/HTMX/Alpine loading, credential wiring, or theme FOUC guards.

**Tag:** `v0.6.12` (identity-adapter composition; multi-user BOM is v0.6.12 / my-auth v0.4.6 / my-usermanager v0.5.8)

---

## Platform stack (what we use)

This package is the thin shared layer in a small platform. Together:

| Piece | Role | How consumers get it |
|-------|------|----------------------|
| **app-factory** (this repo) | Bundled chrome, one FastAPI mount, and the shared Jinja shell | `git` tag `v0.6.12` directly; multi-user hosts follow `COMPAT.md` |
| **basecoat-factory** | Maintainer-only build source for the generated Basecoat/UI asset bundle | Not a runtime dependency |
| **my-auth** (`fastapi-htmx`) | Generic passkey login/register UI | BOM tag `v0.4.6` |
| **my-usermanager** (`fastapi-htmx`) | Generic account/admin UI | BOM tag `v0.5.8` |
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
| Login / register HTML + passkey UI static | **my-auth**, composed by app-factory `install_identity_adapters` |
| Generic account/admin HTML + UI static | **my-usermanager**, composed by app-factory `install_identity_adapters` |
| Domain routes, ORM, product CSS | **the app** |

`install_platform()` is chrome-only. Multi-user hosts call `install_identity_adapters()` with `PasskeyBinding` and/or `UserManagerBinding`; they do not invoke the package installers directly.

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
| `app_factory.responses.htmx_redirect` | Native 303 plus `HX-Redirect` for HTMX full-page navigation |
| `app_factory.csrf.SessionCsrfProtection` | Signed-session CSRF adapter for host forms and my-usermanager |
| `app_factory.cdn` | Optional CDN assets, `cdn_asset()`, SRI verification, `extend_manifest()` / `install_manifest()` |
| `app_factory.jinja` | `configure_jinja_env()` — registers bundled/local and optional CDN helpers plus the template loader |
| `app_factory.fastapi` | `install_app_factory_ui()` — the sole supported FastAPI mount/Jinja integration |
| `app_factory.adapters` | `install_identity_adapters()` plus focused passkey / usermanager / session helpers |
| `app_factory/templates/app_factory/shell.html` | Shared five-block full-page shell |
| `app_factory/templates/app_factory/client_shell.html` | Slim TAP client document (Basecoat + theme/auth; no HTMX/Alpine) |
| `app_factory/templates/app_factory/head_assets_slim.html` | Same-origin Basecoat/icons only (no HTMX/Alpine) |
| `app_factory/templates/app_factory/identity_public_shell.html` | Public activation/recovery frame (brand + theme/locale, no sidebar) |
| `app_factory/templates/app_factory/identity_authenticated_shell.html` | Authenticated account/credentials/users frame (`product_shell` + markers) |
| `app_factory/templates/app_factory/identity_public_state.html` | Non-enumerating invalid/expired capability alert |
| `app_factory/templates/app_factory/identity_denied.html` | Full-page unauthorized state in authenticated chrome |
| `app_factory/templates/app_factory/identity_denied_fragment.html` | HTMX unauthorized/forbidden fragment |
| `app_factory/templates/app_factory/head_assets.html` | Same-origin core CSS/JS tags + HTMX credentials + 401 → login redirect |
| `app_factory/templates/app_factory/theme_boot.html` | Early dark/light/auto FOUC guard (`window.appTheme`) |
| `app_factory/templates/app_factory/shell_boot.html` | Shared shell JS (sidebar, active nav, basecoat, theme clicks) via `window.appShellConfig` |

**Not included:** domain models, product routes, auth ceremony logic, product CSS.

---


## Shared browser mechanisms

- Use `htmx_redirect(request, url)` instead of copying the native/HTMX redirect
  branch into each host.
- Use `SessionCsrfProtection(session_key=...)` when the host already has signed
  `SessionMiddleware`; missing middleware fails explicitly.
- Set `toast_enabled = true` in shell context to install the Basecoat toaster and
  shared `htmx:sendError` / `htmx:timeout` bridge. Override
  `network_error_message` and `toast_region_label` as host copy.
- Import `app_factory/components/pagination.html` for accessible native links
  with optional `hx_target`, `hx_swap`, and `hx_push_url`.

These helpers own transport/session/chrome mechanics only. Hosts still own
route authorization, domain validation, accepted upload formats, and copy.

---

## Bundled core assets (`v0.6.12`)

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

### Reusable file upload

`app_factory/components/file_upload.html` exports domain-blind `file_upload` and `file_upload_field` Jinja macros.
The host configures `accept`, `multiple`, `max_bytes`, labels, action, and HTMX
target. The component provides picker/drop, selected-file removal, batch
confirmation, busy state, and real `htmx:xhr:progress`; the normal multipart
form remains the no-JS fallback. Server-side format and security validation
remain consumer-owned.

Client pages opt into the same HTMX/Alpine generation without forking the shell:

```jinja2
{% set client_interactive = true %}
{% extends "app_factory/client_shell.html" %}
{% from "app_factory/components/file_upload.html" import file_upload %}

{{ file_upload(
    id="evidence",
    action="/evidence",
    accept=".example,application/x-example",
    max_bytes=26214400,
    submit_label="Upload",
) }}
```

The macro does not name or inspect product formats. Browser `accept` is UX only;
the consumer must validate bytes and policy on the server.

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
# pyproject.toml — pin one BOM generation from COMPAT.md / bom/multi_user.toml
dependencies = [
  "app-factory[platform]",
  "my-auth[fastapi-htmx]",
  "my-usermanager[fastapi-htmx,myauth]",
]

[tool.uv]
override-dependencies = ["app-factory[platform]"]

[tool.uv.sources]
app-factory = { git = "https://github.com/mikolaj92/app-factory.git", tag = "v0.6.12" }
my-auth = { git = "https://github.com/mikolaj92/my-auth.git", tag = "v0.4.6" }
my-usermanager = { git = "https://github.com/mikolaj92/my-usermanager.git", tag = "v0.5.8" }
```

```bash
uv lock && uv sync
```

Reference integration (bootstrap, invite activation, credentials, recovery, admin users):
[`examples/multi_user_bom/`](examples/multi_user_bom/).

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

The supported blocks include `title`, `head_assets`, `head_extra`, `body` /
`navigation` / `header` / `content` / `page_scripts` / `loading_label` /
`content_class` / `body_end`, plus product-shell header slots
`header_controls_start` / `header_controls_end` / `sidebar_toggle_icon`.
Signed-in identity and its
deterministic initial avatar render in the sidebar footer; guest users see
login/register there instead. The shell loads theme boot,
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
`platform_menu`, `platform_user`, `platform_paths`, locales. `PlatformPaths`
names the identity lifecycle routes (login, logout, register, activation,
recovery, account, credentials, users, invite). Set `PlatformPaths.root` when
the app sits behind a reverse-proxy prefix. Opt into standard sidebar links with
`enable_account`, `enable_credentials`, `enable_admin_users`, and
`enable_invite`; admin links also require `PlatformUser.is_admin`. Hosts remain
responsible for mapping product authorization to that view. Public guest chrome
never receives authenticated/admin identity navigation. `PlatformUser`
derives a stable background and initial for its high-contrast fallback avatar.
Do not fork sidebar or main-header markup — inject extras only through blocks
(`header_controls_start` for notifications, `body_end` for toasts).

### Slim TAP client shell (no HTMX/Alpine)

Operator `product_shell` / `shell.html` always load HTMX and Alpine via
`head_assets`. TAP client hosts must not fork a private `client_base.html`
to avoid that. Extend the packaged slim document instead:

```html
{% extends "app_factory/client_shell.html" %}
{% block content %}
  <h1>Portal</h1>
  {% include "app_factory/platform_session.html" %}
{% endblock %}
```

This frame keeps theme boot, Basecoat, and `platform_controls` (theme/locale +
auth). It does **not** emit HTMX/Alpine tags or the HTMX loading overlay.
Include `platform_session` on the account/home surface — never in the header.
Constant: `CLIENT_SHELL`.

### Identity lifecycle shells

Public capability pages and authenticated account/admin pages share chrome
without host template forks:

```html
{# Activation / recovery — my-auth panels fill identity_panel #}
{% extends "app_factory/identity_public_shell.html" %}
{% block identity_panel %}
  {% if capability_valid %}
    {# adapter ceremony panel #}
  {% else %}
    {% include "app_factory/identity_public_state.html" %}
  {% endif %}
{% endblock %}
```

```python
# my-usermanager account / users / invite
UserManagerUiConfig(
    base_template="app_factory/identity_authenticated_shell.html",
    # labels=...  # host copy overrides
)
```

Extension points (no forks):

| Need | Mechanism |
|------|-----------|
| Host policy blurb on public pages | `identity_notice` / `identity_footer` blocks |
| Invalid/expired capability copy | `identity_public_state_*` context vars |
| Unauthorized full page | render `identity_denied.html` |
| Unauthorized HTMX fragment | include `identity_denied_fragment.html` |
| Adapter page body | `identity_panel` or `content` block |

Constants: `CLIENT_SHELL`, `IDENTITY_PUBLIC_SHELL`, `IDENTITY_AUTHENTICATED_SHELL`,
`IDENTITY_PUBLIC_STATE`, `IDENTITY_DENIED`, `IDENTITY_DENIED_FRAGMENT`.

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
Hosts call the generic composer once; they do not copy installer glue.

```python
from app_factory.adapters import (
    PasskeyBinding,
    UserManagerBinding,
    install_identity_adapters,
)
from app_factory.csrf import SessionCsrfProtection
from app_factory.platform import PlatformConfig, PlatformPaths
from my_auth.fastapi import PasskeyCookies

installed = install_identity_adapters(
    app,
    environments=[templates.env],
    config=PlatformConfig(
        paths=PlatformPaths(),
        enable_account=True,
        enable_credentials=True,
        enable_admin_users=True,
        enable_invite=True,
    ),
    passkey=PasskeyBinding(
        service=passkey_service,
        hooks=passkey_policy_hooks,  # persistence + session; no render_* stubs
        cookies=PasskeyCookies(secure=cookie_secure),
    ),
    usermanager=UserManagerBinding(
        hooks=user_policy_hooks,  # RBAC catalog + stores
        csrf_protection=SessionCsrfProtection(),
        environment=templates.env,
    ),
    current_user=platform_user_from_request,
)
```

- The installer owns the package-specific static mount; hosts do not mount it manually.
- my-auth’s `fastapi-htmx` extra depends on **app-factory** so package login pages
  use the same Basecoat chrome (`btn`, `card`, dark mode) as host shells.
- Point host links at `platform_paths` (or `PlatformPaths.href`) rather than
  hardcoding `/activate`, `/recover`, `/account/passkeys`, or admin invite URLs.
  Activation and recovery remain public capability pages owned by my-auth; account
  credentials and users/invite remain adapter-owned. Compose them into
  `identity_public_shell` / `identity_authenticated_shell` so hosts do not ship
  custom lifecycle chrome.

---

## Recommended app checklist

1. Depend on the multi-user BOM pins from `COMPAT.md` / `bom/multi_user.toml` (with `override-dependencies`).
2. Call `install_identity_adapters()` (or `install_platform()` for chrome-only) once with every Jinja environment.
3. Extend identity shells for lifecycle pages; keep navigation data-driven via `PlatformPaths`.
4. Supply passkey/usermanager **policy** hooks only — do not call `install_passkey_ui` / `install_usermanager_ui` from the host.
5. Keep only product CSS and product CDN extras in the app.
6. Contract-test that canonical local assets and enabled UI routes return 200 (see `examples/multi_user_bom`).

---

## API sketch

install_identity_adapters(app, environments, config, passkey, usermanager, current_user) -> IdentityInstall
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
| **v0.6.12** | **1.0.2** | Additive on v0.6.11: `install_identity_adapters` + focused passkey/usermanager/session helpers; BOM row my-auth v0.4.6 / my-usermanager v0.5.8. No chrome change. |
| **v0.6.11** | **1.0.2** | Shared browser mechanisms (HTMX redirect, session CSRF, toast boot, pagination). Multi-user BOM stayed on v0.6.10 until matching auth tags; chrome generation with my-auth v0.4.6 / my-usermanager v0.5.7 had no composer. |
| **v0.6.7** | **1.0.2** | Additive on v0.6.6: BOM row my-auth v0.4.5 / my-usermanager v0.5.6 (nested chrome v0.6.6; initialize() stamps enrollment on current schemas). No chrome change. |
| **v0.6.6** | **1.0.2** | Additive on v0.6.5: slim TAP `client_shell` (no HTMX/Alpine) + `PlatformPaths.invite` default `/admin/users`; same my-auth v0.4.2 / my-usermanager v0.5.4 |
| **v0.6.5** | **1.0.2** | Multi-user platform BOM + enrollment capability DDL in ensure_sqlite_schema (my-auth v0.4.2) + nested my-auth pin (my-usermanager v0.5.4); hosts override app-factory only |
| **v0.6.4** | **1.0.2** | Multi-user platform BOM + packaged ceremony shells (my-auth v0.4.1) + invitation DDL in SQLiteAuthDatabase (my-usermanager v0.5.2) |
| **v0.6.3** | **1.0.2** | Multi-user platform BOM + packaged invite admin (my-usermanager v0.5.1, my-auth v0.4.0) |
| **v0.6.2** | **1.0.2** | Multi-user platform BOM + identity lifecycle shells/paths |
| v0.5.19 | 1.0.2 | Full Basecoat + HTMX + Alpine + app shell + Material Symbols Outlined v364; hard pytest no-npm contract |
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
# plist: example/dev.app-factory.storybook.plist (repo $HOME/Developer/app-factory, or APP_FACTORY_ROOT)

# Regenerate bundled platform assets
uv run python scripts/refresh_platform_assets.py
```

The `example/` package is a small FastAPI host that mounts the real product
shell and walks guest/signed-in/bare/account/HTMX/locale/component states.
Use it as the default place to visual-check chrome changes before tagging.
`pythonpath = ["."]` keeps `example.app` importable for pytest and uvicorn.

The `examples/multi_user_bom/` package is the pinned multi-user BOM consumer
(app-factory + my-auth + my-usermanager). Prefer it when checking identity
lifecycle composition and package resolution (`uv lock` + pytest there).

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
