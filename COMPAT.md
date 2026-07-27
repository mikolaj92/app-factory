# Platform BOM / compatibility matrix

Single source of truth for host pins when using `app-factory[platform]`.

| app-factory | my-auth | my-usermanager | Notes |
|-------------|---------|----------------|-------|
| **v0.5.4** | **v0.3.10** | **v0.3.2** | Grouped HTMX sidebar (`MenuGroup`) + Alpine afterSwap reinit in head_assets |
| v0.5.3 | v0.3.9 | v0.3.2 | Header theme/locale; foot Login/Account; **Log out only on account page** |
| v0.5.2 | v0.3.8 | v0.3.1 | Header theme/locale; foot had logout (superseded) |
| v0.5.1 | v0.3.7 | v0.3.1 | All chrome in platform foot (superseded) |
| v0.5.0 | v0.3.6 | v0.3.1 | Platform composition + product shell foot |

## Host rule

Prefer:

```toml
dependencies = ["app-factory[platform]"]
[tool.uv.sources]
app-factory = { git = "https://github.com/mikolaj92/app-factory", tag = "v0.5.4" }
```

Do **not** float `my-usermanager` on `branch = "main"` for production hosts.
Do **not** re-copy theme boot or platform foot templates into hosts.

### Chrome placement (hosts must not fork)

| Surface | Partial | Contents |
|---------|---------|----------|
| **Main header** | `platform_theme_locale` | language (optional) + icon theme toggle |
| **Sidebar foot** | `platform_auth` | guest: Login (+ Register); signed-in: **Account link only** (name) |
| **Account page** | `platform_session` | **Log out** form (only place) |
| **No-sidebar shells** | `platform_controls` | theme/locale + auth (still no logout — include `platform_session` on the account/home surface) |

Forbidden host forks: theme in sidebar, logout in nav menu, logout next to the account name in the foot.
