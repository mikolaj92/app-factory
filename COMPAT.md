# Platform BOM / compatibility matrix

Single source of truth for host pins when using `app-factory[platform]`.

| app-factory | my-auth | my-usermanager | Notes |
|-------------|---------|----------------|-------|
| **v0.5.2** | **v0.3.7** | **v0.3.1** | Header: locale + theme (icons); sidebar foot: login/logout only |
| v0.5.1 | v0.3.7 | v0.3.1 | All chrome in platform foot (superseded — theme buried in sidebar) |
| v0.5.0 | v0.3.6 | v0.3.1 | Platform composition + product shell foot |

## Host rule

Prefer:

```toml
dependencies = ["app-factory[platform]"]
[tool.uv.sources]
app-factory = { git = "https://github.com/mikolaj92/app-factory", tag = "v0.5.2" }
```

Do **not** float `my-usermanager` on `branch = "main"` for production hosts.
Do **not** re-copy theme boot or platform foot templates into hosts.
Chrome placement (hosts must not fork):
- **Main header** — `platform_theme_locale` (language + icon theme toggle)
- **Sidebar foot** — `platform_auth` (login / account / logout)
- **No-sidebar shells** — `platform_controls` (both)
