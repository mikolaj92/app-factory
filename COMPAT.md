# Platform BOM / compatibility matrix

Single source of truth for host pins when using `app-factory[platform]`.

| app-factory | my-auth | my-usermanager | Notes |
|-------------|---------|----------------|-------|
| **v0.5.1** | **v0.3.7** | **v0.3.1** | Platform foot owns locale + theme + login/logout (not the main header) |
| v0.5.0 | v0.3.6 | v0.3.1 | Platform composition + product shell foot |

## Host rule

Prefer:

```toml
dependencies = ["app-factory[platform]"]
[tool.uv.sources]
app-factory = { git = "https://github.com/mikolaj92/app-factory", tag = "v0.5.1" }
```

Do **not** float `my-usermanager` on `branch = "main"` for production hosts.
Do **not** re-copy theme boot or platform foot templates into hosts.
Do **not** put theme / language / login / logout controls in the main header —
they live only in `platform_sidebar_foot` (or `platform_controls` on shells
without a sidebar).
