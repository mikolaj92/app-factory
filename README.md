# app-factory

Shared **chrome** for FastAPI + Jinja + HTMX + Alpine + [basecoat-factory](https://github.com/mikolaj92/basecoat-factory) apps
(rnkstr, wolnyrolnik, emitype, Temida/Argus, …).

## What you get

| Module | Purpose |
|--------|---------|
| `app_factory.cdn` | Pinned jsDelivr assets (factory CSS/JS, htmx, alpine) + SRI verify |
| `app_factory.jinja` | `configure_jinja_env` → `cdn_asset` / template partials |
| `app_factory/templates/app_factory/*` | `head_assets.html`, `theme_boot.html` |

**Not included:** domain models, product routes, product-only CSS.

**my-auth:** extra `fastapi-htmx` depends on this package so default `/login` and
`/register` pages load the same Basecoat chrome as host apps (`btn`, `card`, dark mode).

## Install (path / editable)

```toml
# pyproject.toml
dependencies = ["app-factory"]

[tool.uv.sources]
app-factory = { path = "../app-factory", editable = true }
```

```bash
uv sync
```

## Wire Jinja

```python
from fastapi.templating import Jinja2Templates
from app_factory import configure_jinja_env, CDN_ASSET_MANIFEST, cdn_asset

templates = Jinja2Templates(directory="templates")
configure_jinja_env(templates.env)
# or re-export:
# templates.env.globals["cdn_asset"] = cdn_asset
```

## Wire templates

```html
<head>
  {% include "app_factory/theme_boot.html" %}
  <title>{% block title %}App{% endblock %}</title>
  {% include "app_factory/head_assets.html" %}
  {% block head_extra %}{% endblock %}
</head>
<body class="app-shell">
  {% block body %}{% endblock %}
</body>
```

Optional product CSS:

```jinja
{% set product_css_url = "/static/css/product.css" %}
{% include "app_factory/head_assets.html" %}
```

## Optional CDN extras

```python
from app_factory.cdn import extend_manifest, install_manifest

install_manifest(extend_manifest(["chartjs"]))
```

## Pin

Core CSS/JS: **basecoat-factory@v0.2.0** (jsDelivr).
