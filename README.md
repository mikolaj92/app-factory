# app-factory

Shared **frontend chrome** as files: HTML/Jinja templates, bundled CSS/JS, and
an HTTP contract. FastAPI + Jinja2 is one language binding (`app_factory[platform]`),
not the source of truth. Another language clones the git tag and reads the same
files.

The goal is one place to ship same-origin chrome so product apps do **not**
re-implement Basecoat/HTMX/Alpine loading, credential wiring, or theme FOUC guards.

**Tag:** `v0.7.9`. Companions: my-auth `v0.5.7` / my-usermanager `v0.6.10`; pins: [`bom/multi_user.toml`](bom/multi_user.toml). This is the library BOM, not confirmation of product rollout.

---

## Platform stack (what we use)

This package is the thin shared layer in a small platform. Together:

| Piece | Role | How consumers get it |
|-------|------|----------------------|
| **app-factory** (this repo) | Chrome files + HTTP contract; FastAPI binding is optional | `git` tag `v0.7.9` directly; multi-user hosts follow `COMPAT.md` |
| **basecoat-factory** | Historical palette/layout notes; not a runtime or host dependency | Not used at runtime |
| **my-auth** (`fastapi-htmx`) | Generic passkey login/register UI | BOM tag `v0.5.7` |
| **my-usermanager** (`fastapi-htmx`) | Generic account/admin UI | BOM tag `v0.6.10` |
| **FastAPI + Jinja2 + HTMX + Alpine** | Server-rendered app shell | App code; core scripts/CSS served by the app |

### Dependency rule

- **Libraries and apps:** install via **git tags / branches** (or published tags), **not** `path = "../..."`.
- **Core CSS/JS chrome:** serve the files bundled in app-factory from the same origin; do not copy them into each app.
- **Product-only** assets stay in the app (domain CSS, charts, maps, icons).

### What lives where

| Concern | Owner |
|---------|--------|
| Bundled Basecoat UI / HTMX / Alpine files + manifest | **app-factory** `assets/` |
| Identity paths, HTMX redirect, Origin CSRF, Jinja subset | **app-factory** `contract/` |
| Shared `<head>`, shell, optional CDN pins, and theme boot | **app-factory** `templates/` |
| FastAPI mount / Jinja renderer / identity composer | **app-factory** `[platform]` binding |
| Login / register HTML + passkey UI static | **my-auth**, composed by app-factory `install_identity_adapters` |
| Generic account/admin HTML + UI static | **my-usermanager**, composed by app-factory `install_identity_adapters` |
| Domain routes, ORM, product CSS | **the app** |

`install_platform()` is chrome-only. Multi-user hosts call `install_identity_adapters()` with `PasskeyBinding` and/or `UserManagerBinding`; they do not invoke the package installers directly.

Do not ship local platform shells, runtime dependencies on basecoat-factory, private copies of bundled `basecoat.css` / HTMX / Alpine, replacement full-page passkey login, or copied optional CDN pins (use `app_factory.cdn`).

---

## What this package exports

| Module / path | Purpose |
|---------------|---------|
| `app_factory/contract/` | Language-neutral paths, HTTP rules, Jinja subset (`paths.toml`, `http.toml`) |
| `app_factory.assets` | Verified bundled core assets, URL helper, and lazy Starlette static app |
| `app_factory.responses.htmx_redirect` | Native 303 plus `HX-Redirect` for HTMX full-page navigation |
| `app_factory.responses.login_redirect` | 303 to login with same-origin `?next=` and `HX-Redirect` for HTMX swaps |
| `app_factory.responses.template_response` | Explicit full-page/HTMX-fragment renderer with request-local platform context |
| `app_factory.csrf.SameOriginCsrfMiddleware` | Origin/Referer protection for unsafe cookie-session requests |
| `app_factory.csrf.SessionCsrfProtection` | Signed-session CSRF adapter for host forms and my-usermanager |
| `app_factory.uploads.read_upload_bounded` / `read_uploads_bounded` | Bounded in-memory read of one upload or a count/per-file/aggregate-limited batch; format policy stays host-owned |
| `app_factory.cdn` | Optional CDN assets, `cdn_asset()`, SRI verification, `extend_manifest()` / `install_manifest()` |
| `app_factory.jinja` | `configure_jinja_env()` — registers bundled/local and optional CDN helpers plus the template loader |
| `app_factory.fastapi` | `install_app_factory_ui()` — the sole supported FastAPI mount/Jinja integration |
| `app_factory.create_product_app` / `install_product_host` | Thin product host from one `ProductAppConfig` (chrome, health, Origin CSRF, HTMX errors) |
| `app_factory.runs.RunPort` | Host-owned async run adapter; opt-in `create_run_router` / `create_run_view_router` |
| `app_factory.intake.IntakeSpec` | Declarative single-form contract; `create_intake_router` mounts GET form + POST start |
| `app_factory.conformance.check_thin_host` | Source + live-app check that the host did not fork chrome or skip the thin-host contract |
| `app_factory.conformance.assert_public_origin_csrf` | Probe public Origin against a different backend HTTP base URL (TLS terminator vs uvicorn) |
| `app_factory.adapters` | `install_identity_adapters()` plus focused passkey / usermanager / session helpers |
| `app_factory/templates/app_factory/product_shell.html` | Canonical logged-in product chrome (sidebar + header + main); prefer this for new products |
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
- Use `SameOriginCsrfMiddleware` instead of copying Origin/Referer middleware
  into each cookie-session host. Pass trusted origins and webhook exemptions
  explicitly; the current request origin is accepted automatically.
- Use `assert_public_origin_csrf(...)` instead of probing Origin CSRF against
  `http://testserver`. The public origin must differ from the backend base URL.
- Use `template_response(...)` for an explicit page/fragment pair. Dynamic
  request values come from `request.state.app_factory_platform_context`.
  `install_platform()` still seeds request-agnostic chrome defaults into Jinja
  globals through `apply_platform_context`.
- Set `toast_enabled = true` in shell context to install the Basecoat toaster and
  shared `htmx:error` / `htmx:response:error` bridge. Override
  `network_error_message` and `toast_region_label` as host copy.
- Import `app_factory/components/pagination.html` for accessible native links
  with optional `hx_target`, `hx_swap`, and `hx_push_url`.

These helpers own transport/session/chrome mechanics only. Hosts still own
route authorization, domain validation, accepted upload formats, and copy.

---

## Bundled core assets (`v0.7.9`)

The wheel ships all core files. `MANIFEST.json` pins filenames, versions, and
SHA-384 digests; the runtime verifies it on first access.

| Name | Package / version | Kind |
|------|-------------------|------|
| `basecoat-css` | basecoat-css **1.0.2** published dist + factory `.app-*` layout | style |
| `basecoat-js-all` | basecoat-css **1.0.2** | script |
| `lism-layout` | lism-css **1.0.1** published layout primitives only + factory spacing/token bridge (no reset or palette) | style |
| `tailwind-browser` | `@tailwindcss/browser` **4.3.3** (registry tarball at refresh) | script |
| `htmx` | HTMX **4.0.0** (GitHub dist) | script |
| `alpine` | Alpine.js **3.17.2** (registry tarball at refresh) | script |
| `landing-css` | factory landing **1.0.0** (landing page only, not `head_assets.html`) | style |
| `landing-js` | factory landing **1.0.0** (landing page only, not `head_assets.html`) | script |

Icons in chrome and shared components are **inline Lucide SVGs** (the Basecoat-recommended set). The factory does not ship an icon font or a live CDN icon kit.

```python
from app_factory import bundled_asset, list_bundled_assets, platform_asset_url

css = bundled_asset("basecoat-css")
url = platform_asset_url(css.name)  # /static/platform/basecoat-factory.min.css
tw = bundled_asset("tailwind-browser")
platform_asset_url(tw.name)  # /static/platform/tailwind.min.js
```

Exact sources, licenses, and digests are stored under `app_factory/assets/`.

### Reusable file upload

`app_factory/components/file_upload.html` exports `file_upload` / `file_upload_field`; hosts supply action, target, `accept`, `multiple`, `max_bytes`, and labels. Native multipart POST is the no-JS fallback.
This contract comes from `file_upload_boot.html` and bundled `assets/htmx.min.js` (4.0.0), not a browser run. It establishes no observed POST counts or one-POST-per-confirmation guarantee.

- In the shared head, HTMX registers its `DOMContentLoaded` listener before the upload boot, so its form `submit` handler precedes the controller's on initial page load.
  HTMX checks native validity and collects `FormData` before `htmx:config:request`, then emits
  `htmx:before:request` before Fetch. These request events carry `event.detail.ctx`;
  use `ctx.sourceElement`, `ctx.request.body`, and (once received) `ctx.response.status`.
- The multipart body contains named form fields, repeated files under `name` (default `files`),
  and, with `multiple`, hidden `confirmed_count`. This is a collection-time snapshot, not a live file list.
  The controller validates live `input.files` on both `submit` and `htmx:before:request`:
  required selection, per-file `max_bytes`, then case-insensitive extension/MIME/`type/*` matching.
  It does not rebuild the collected body; later file or confirmation changes need not reach that body.
- For batches, a count mismatch cancels that event and opens `window.confirm`; acceptance stores
  the count and calls `form.requestSubmit()`. Cancellation does not stop other listeners, and this
  HTMX submit path does not test `submit.defaultPrevented`. Re-entry during native submit can be
  suppressed; re-entry from `htmx:before:request` can queue another request (default `queue first`).
  Queued contexts retain collected bodies and rerun before-request handlers, not data collection.
- Picker change, drop, or removal clears status and confirmation, not busy/progress. Confirmation
  compares only counts, not file identity. Retry is manual: retained forms keep files and confirmation;
  validation runs again, but an unchanged confirmed count skips the dialog. There is no automatic retry.
- Cancelling `htmx:before:request` prevents that Fetch, not queued work. Earlier listeners leave
  `defaultPrevented` set, so the controller skips busy/progress; later listeners can cancel after it
  sets busy. Form-local resets handle `htmx:after:request` after response text, before swap, and
  `htmx:finally:request` on completion, error, timeout, abort, or before-request cancellation.
  Reset clears busy, restores required/empty disabling, hides progress, and sets `0`/`0%`.
  Native validation/config cancellation never enters finally. After swap, detached sources dispatch
  on `document` or a replacement target, so the old form's reset listener may not receive finally.
- Boot/field-ready guards prevent repeat field initialization, not one listener per form: each field adds form handlers using the first status/submit/confirmation/progress controls.
  Fields share a count, not batch identity; each render/reset can overwrite submit disabling. Swap initialization scans descendants of `ctx.target || ctx.sourceElement`, excluding the root.

Client pages set `client_interactive = true` and extend `app_factory/client_shell.html`. Server helpers enforce size/count limits; hosts validate content. Client checks and `confirmed_count` are not security controls.

### Shared presentation contract (Basecoat-first, no per-app CSS toolchain)

Products link the factory CSS/JS bundle only. They do **not** install Tailwind
or Basecoat. Layout and chrome come from this package; UI components come from
Basecoat inside the same bundle.

| Layer | Use | Examples |
|-------|-----|----------|
| **UI components** | Basecoat | `.card`, `.btn`, `.input`, `.field`, `.table` + `.table-container`, `.sidebar`, `.dialog`, … |
| **Layout primitives** | published Lism layout-only CSS | `.l--stack`, `.l--cluster`, `.l--center`, `.l--autoColumns`, `.l--withSide`, `.l--switchColumns` |
| **Legacy layout** | existing `.app-*` kept for compatibility | `.app-page`, `.app-stack`, `.app-header`, `.app-cluster`, `.app-card-grid`, `.app-form__field` |
| **Shell chrome** | factory only | `.app-shell`, `.app-main*`, sidebar brand/foot glue, theme/locale |
| **Extra utilities** | bundled Tailwind browser engine | any Tailwind class on host HTML; no safelist, no host CSS toolchain |

New layouts use Lism primitives instead of handwritten flex/grid rules. Basecoat
still owns component anatomy and padding; Tailwind utilities remain available.
One container has one layout owner: do not combine `.l--autoColumns` with
`.app-card-grid`. Set `--cols`, `--sideW`, `--mainW`, `--breakSize`, or
`--layout-gap` in a product stylesheet (HTML/CSS stay separate). Layout defaults
supply only the three tokens needed by the published primitives; no Lism reset,
color palette, typography, React, or runtime JavaScript is included.
The default stack/grid gap is 1.5rem; cluster gap is 0.75rem. Existing
`app-stack--tight/sm/compact/section` spacing modifiers can tune `.l--stack`.
`autoColumns` defaults to 20rem minimum columns and follows available width,
not the viewport. `withSide` requires one direct `.is--side` child.

Lism is served before Basecoat to establish cascade order:
`theme → base → components → layout → utilities`. Component internals remain
Basecoat-owned; explicitly selected layout primitives override component layout,
Tailwind utilities can tune them, and unlayered host styles retain precedence.

Also shipped for product surfaces without inventing a second design system:

- `.app-table-wrap` — overflow boundary for wide tables (Basecoat `.table-container` is equivalent; either is fine)
- `.app-dropzone` — native file-input label / drag target (`data-dragover="true"`)
- `.app-progress` — native `<progress>` styling (Basecoat `.progress` is the div+span pattern)

Do **not** add new `.app-*` components for things Basecoat already has.
Product-specific statuses and actions stay in product HTML with Basecoat
variants or semantic `data-*` attributes. Importing app-factory does not fetch
the network. Explicit `verify_cdn_asset()` may fetch a pinned jsDelivr URL.

### Optional CDN extras

Optional product integrations remain pinned on jsDelivr and are absent from
the default manifest:

| Name | Notes |
|------|--------|
| `chartjs` | Chart.js 4.5.1 |
| `leaflet-css` / `leaflet-js` | Leaflet 1.9.4 |
| `sortablejs` | SortableJS 1.15.7 |

```python
from app_factory.cdn import cdn_asset, extend_manifest, install_manifest

install_manifest(extend_manifest(["chartjs", "leaflet-css", "leaflet-js"]))
chart = cdn_asset("chartjs")
```

Call `verify_cdn_asset()` or `verify_cdn_manifest()` explicitly in release or
deploy checks. Product templates load extras after the factory head include.

---
## Install (git + uv)

Pin one tagged BOM generation, not a local path; then run `uv lock && uv sync`:
```toml
# pyproject.toml; compatibility rules: COMPAT.md; reference: examples/multi_user_bom/
dependencies = ["app-factory[platform]", "my-auth[fastapi-htmx]", "my-usermanager[fastapi-htmx,myauth]"]
[tool.uv]
override-dependencies = ["app-factory[platform]"]
[tool.uv.sources]
app-factory = { git = "https://github.com/mikolaj92/app-factory.git", tag = "v0.7.9" }
my-auth = { git = "https://github.com/mikolaj92/my-auth.git", tag = "v0.5.7" }
my-usermanager = { git = "https://github.com/mikolaj92/my-usermanager.git", tag = "v0.6.10" }
```

New products use `create_product_app(...)`, one `ProductAppConfig`, and `app_factory/product_shell.html` (see [`examples/minimal_host/app.py`](examples/minimal_host/app.py)); add identity bindings without copying installers.
Existing products must update all three pins and their lock, then replace repeated card/form/content layouts with Lism; loading its asset alone is not adoption.

---

## Thin product host

```python
from pathlib import Path
from fastapi import APIRouter, Request
from app_factory import ProductAppConfig, create_product_app, template_response
from app_factory.platform import MenuItem, PlatformConfig

router = APIRouter()

@router.get("/")
def home(request: Request):
    return template_response(
        request.app.state.app_factory_product.environment, request, "home.html"
    )

app = create_product_app(
    ProductAppConfig(
        template_directory=Path("templates"),
        platform=PlatformConfig(app_name="My product", menu=(MenuItem("Home", "/"),)),
    ),
    routers=(router,),
    # lifespan=host_lifespan,  # ordinary FastAPI async context manager
)
```

This composes the existing installers: shared Jinja loader and same-origin
assets, request-local user/locale context and theme chrome, strict Origin CSRF,
standard HTTP/validation/500 handlers, and `GET /health` (`{"status": "ok"}`).
Health is liveness only; it does not probe a product database. JSON clients retain
FastAPI HTTP/422 semantics; HTMX receives escaped alert fragments. Unexpected
errors return generic 500 copy, never exception details. The shared shell also
shows a safe, localized `network_error_message` in the HTMX target on failed
requests, preserving the form for retry. It never swaps raw error responses
(proxy HTML, JSON, or tracebacks); no per-product error JavaScript is needed.

Pass `passkey=PasskeyBinding(...)`, `usermanager=UserManagerBinding(...)`,
`current_user=...`, and `locales=...` to opt into identity via
`install_identity_adapters`. The usermanager environment defaults to the host's
shared environment. Auth services, stores, RBAC hooks, session transport and
form-token protection remain host-supplied; no database or auth ceremony is
created. For signed sessions, add `SessionMiddleware` **after** composition
(install `itsdangerous` in the host), and pass `SessionCsrfProtection()` in the
identity bindings. Origin CSRF is always on; configure trusted origins or webhook
prefix exemptions explicitly with `csrf_trusted_origins` / `csrf_exempt_prefixes`.
Exemption prefixes are literal request paths, including any deployment prefix.

`PlatformPaths.root` is the **route prefix** for domain routers, identity, health
and static (the same convention as existing identity adapters), not FastAPI's
ASGI `root_path`. Do not prefix supplied domain routers twice. Menu/brand URLs
remain explicit host navigation data. A proxy must preserve this prefix.

For an existing FastAPI app use `install_product_host(app, config, ...)`; its
lifespan is left intact. The result (also `app.state.app_factory_product`) exposes
`environment`, `platform`, and optional `identity`. Install before startup and
before any lower-level factory installers. Compatible repeats with the same
router objects and bindings return the same result without adding middleware or
routes. Changed inputs, existing factory installations, custom standard error
handlers and overlapping paths/mounts raise `ValueError`. Adapter route conflicts
are checked using installed paths and methods, including earlier dynamic routes
and root mounts. Disjoint HTTP methods and later catch-alls are allowed by the
identity composer. `check_thin_host(..., identity=True)` repeats the ordered
identity check, detecting shadowing introduced after composition. These checks
can only run after adapter installation; discard an app after a failed
install rather than retrying it. Configure custom error handlers after bootstrap
when deliberately replacing the defaults.

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

The identity composer selects `identity_authenticated_shell.html` for my-usermanager account, users and invite pages.

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

- Emits URLs for the six head pins (`lism-layout`, `basecoat-css`, `basecoat-js-all`, `tailwind-browser`, `htmx`, `alpine`) under the installer-bound prefix. That is not the full `MANIFEST.json` set: `landing-css` and `landing-js` stay on the landing template.
- Optional single product stylesheet via template variable:

  ```jinja
  {% set product_css_url = "/static/css/product.css" %}
  {% include "app_factory/head_assets.html" %}
  ```

- Configures HTMX 4 same-origin credentials and keeps 4xx/5xx from swapping.
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

Shell layout classes (`.app-shell`, page chrome, etc.) ship in the committed
bundle under `app_factory/assets/`; hosts do not vendor chrome.

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
6. Verify each host's full suite and container-width/mobile/light/dark/HTMX geometry; record its PR and results separately. The BOM example does not verify the [named rollout exceptions](COMPAT.md#host-rule), and tests do not prove deployment.

---

## API sketch

create_product_app(config, routers=..., passkey=..., usermanager=...) -> FastAPI
install_product_host(app, config, ...) -> ProductInstall
install_identity_adapters(app, environments, config, passkey, usermanager, current_user) -> IdentityInstall
install_app_factory_ui(app, environments, static_path, mount_name) -> AppFactoryUi
RunPort / create_run_router / create_run_view_router
IntakeSpec / create_intake_router
check_thin_host(app, host_root, identity=...) -> HostConformanceReport
assert_public_origin_csrf(app, public_origin=..., mutation_path=..., backend_base_url=...)
template_response / htmx_redirect
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
| **v0.7.9** | **1.0.2** | Current: pinned Lism 1.0.1 layout-only CSS; shared views and catalog adopt adaptive layouts. Basecoat components, arbitrary Tailwind utilities, and legacy `.app-*` remain compatible. |
| **v0.7.8** | **1.0.2** | `verify_cdn_asset` rejects a version or kind that differs from the approved pin even when the URL matches. Same companions as v0.7.7. |
| **v0.7.7** | **1.0.2** | Chrome contract in files (`contract/paths.toml`, `contract/http.toml`, templates). FastAPI is one binding. Same companions as v0.7.6. |
| **v0.7.6** | **1.0.2** | Same-origin `/favicon.ico` plus `login_redirect` (`?next=` and `HX-Redirect`). Same companions as v0.7.5. |
| **v0.7.5** | **1.0.2** | `assert_public_origin_csrf` probes public Origin vs a different backend HTTP base URL. Same companions as v0.7.4. |
| **v0.7.4** | **1.0.2** | `identity_authenticated_shell` loads `usermanager-ui.css` when `static_url_path` is set. |
| **v0.7.3** | **1.0.2** | Companion my-usermanager `v0.6.7` (`install_local_identity`, durable OIDC flows, unlink-aware account UI). Chrome omitted `usermanager-ui.css`. |
| **v0.7.2** | **1.0.2** | Invite default `/admin/users`; `install_manifest` exported; preferred BOM tags exist in git. Same Tailwind `@layer` contract as v0.7.1. |
| **v0.7.1** | **1.0.2** | Tailwind virtual imports stay in `@layer`; same `create_product_app` / `RunPort` / `template_response` contract as v0.7.0. |
| **v0.7.0** | **1.0.2** | Same-origin Tailwind browser engine instead of a CSS safelist. |
| **v0.6.23** | **1.0.2** | Thin product host + opt-in run/intake views. Same my-auth v0.5.4 / my-usermanager v0.6.5. |
| **v0.6.22** | **1.0.2** | Request-safe app framework: request-local Jinja context, Origin CSRF, bounded uploads. |
| **v0.6.16** | **1.0.2** | Additive on v0.6.11: `install_identity_adapters` + focused passkey/usermanager/session helpers; BOM row my-auth v0.4.8 / my-usermanager v0.5.31. No chrome change. |
| **v0.6.11** | **1.0.2** | Shared browser mechanisms (HTMX redirect, session CSRF, toast boot, pagination). Multi-user BOM stayed on v0.6.10 until matching auth tags; chrome generation with my-auth v0.4.8 / my-usermanager v0.5.7 had no composer. |
| **v0.6.7** | **1.0.2** | Additive on v0.6.6: BOM row my-auth v0.4.5 / my-usermanager v0.5.6 (nested chrome v0.6.6; initialize() stamps enrollment on current schemas). No chrome change. |
| **v0.6.6** | **1.0.2** | Additive on v0.6.5: slim TAP `client_shell` (no HTMX/Alpine) + `PlatformPaths.invite` default `/admin/users`; same my-auth v0.4.2 / my-usermanager v0.5.4 |
| **v0.6.5** | **1.0.2** | Multi-user platform BOM + enrollment capability DDL in ensure_sqlite_schema (my-auth v0.4.2) + nested my-auth pin (my-usermanager v0.5.4); hosts override app-factory only |
| **v0.6.4** | **1.0.2** | Multi-user platform BOM + packaged ceremony shells (my-auth v0.4.1) + invitation DDL in SQLiteAuthDatabase (my-usermanager v0.5.2) |
| **v0.6.3** | **1.0.2** | Multi-user platform BOM + packaged invite admin (my-usermanager v0.5.3, my-auth v0.4.0) |
| **v0.6.2** | **1.0.2** | Multi-user platform BOM + identity lifecycle shells/paths |
| v0.5.39 | 1.0.2 | Full Basecoat + HTMX + Alpine + app shell + Material Symbols Outlined v364; chrome is committed dist |
| v0.5.37 | 1.0.2 | Basecoat-first contract docs + CSS keep-list |

Chrome is committed dist in `app_factory/assets/`. There is no Node toolchain
in this repo: no `package.json`, no lockfile, no compile step for hosts.
Bump those files only through `uv run python scripts/refresh_platform_assets.py`,
which copies pinned published dist (GitHub / registry tarball) plus factory
layout CSS, records licenses and SHA-384 digests, and replaces `app_factory/assets/`
after validation.

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

# Check stable HTTP releases against both committed locks (nonzero on backlog)
uv run --extra dev python scripts/refresh_platform_assets.py --check-http-releases

# Upgrade HTTP packages, then validate both projects before committing
uv lock --upgrade-package fastapi --upgrade-package starlette --upgrade-package uvicorn --upgrade-package httpx2
uv lock --project examples/multi_user_bom --upgrade-package fastapi --upgrade-package starlette --upgrade-package uvicorn --upgrade-package httpx2

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
Installation is not test execution. Validate the two projects separately:

```bash
# Repository root: full suite, including browsers, and all public extras
uv lock --check
uv sync --frozen --all-extras
uv run --locked playwright install --with-deps chromium
uv run --locked --all-extras pytest -q
uv run --locked ruff check .
uv run --locked python scripts/refresh_platform_assets.py --check-http-releases
uv build

# Separate project: use its own cwd, environment, lock and full suite
(cd examples/multi_user_bom && uv lock --check && uv sync --frozen --all-extras && uv run --locked --all-extras pytest -q)
```

After setup, `uv run --locked python scripts/run_projects.py` runs both full suites.
CI executes `uv run --locked --all-extras pytest -q` directly in two steps:
repository root, then `examples/multi_user_bom`, each with its own environment.
It disables uv env-file loading in both projects.
The BOM step also runs after a root failure; each step preserves pytest's
failure status through the log pipeline. CI uploads both pytest summaries
as `project-tests-<SHA>-python-<version>`, including on failure.
The Python 3.12 and 3.14 matrix runs both projects independently.
Separate root and BOM logs record each cwd, argv and exit status.
Omit `--project` to execute both suites even if the first fails.
It overrides inherited `UV_PROJECT_ENVIRONMENT` per project
and removes inherited `UV_WORKING_DIR` and `UV_PROJECT`, including for nested
`uv` commands. It removes `UV_NO_PROJECT` so project discovery cannot be bypassed.
It also removes `UV_NO_SYNC` and `UV_FROZEN` so callers cannot
skip lock validation or conflict with `--locked`. It removes `PYTEST_ADDOPTS`
so inherited selection or collection-only options cannot bypass full execution.
It removes `UV_NO_SOURCES` and `UV_NO_SOURCES_PACKAGE` so the BOM keeps
its declared Git and editable path sources. It also removes inherited
`UV_NO_DEV`, `UV_NO_GROUP` and `UV_NO_DEFAULT_GROUPS` dependency selectors.
It removes `UV_ENV_FILE` and forces `UV_NO_ENV_FILE=1` so env files cannot
restore those options in child or nested `uv` commands.
It checks locked manifests
and returns nonzero if either invocation fails.
Each suite has a 240-second timeout, leaving time within Lokay's 600-second
command budget. A timeout or launch error does not prevent the other suite
from running. Each cwd marker precedes a real pytest invocation; a marker
alone proves nothing. After each invocation, `LOKAY_TEST_EXIT_CODE` records its
exit code and cwd (124 for timeout, 127 for launch failure).
Each `PROJECT_TEST_RESULT=` JSON line records the actual argv, cwd, child PID
and exit code. A null PID means launch failed; a PID alone does not prove
that tests passed. These status lines do not replace pytest summaries. For checkout-local Chromium downloads, set
`PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright"` during installation and execution;
the downloaded browser directory is ignored by Git.

Optional browser isolation (issue #9) skips unless Playwright is installed:

```bash
uv sync --extra browser
uv run playwright install chromium
uv run pytest tests/test_browser_chrome.py tests/test_browser_errors.py tests/test_browser_runs.py
```

---

## Related

- [basecoat-factory](https://github.com/mikolaj92/basecoat-factory) — historical palette/layout notes, not a host dependency  
- [my-auth](https://github.com/mikolaj92/my-auth) — passkeys + fastapi-htmx UI  
- [my-usermanager](https://github.com/mikolaj92/my-usermanager) — users, grants, session principal  
