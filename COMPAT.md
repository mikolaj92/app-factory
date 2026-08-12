# Platform BOM / compatibility matrix

Single source of truth for host pins when using `app-factory[platform]`.

| app-factory | my-auth | my-usermanager | Contract |
|-------------|---------|----------------|----------|
| **v0.6.1** | **v0.3.25** | **v0.4.5** | Shared identity shells: public activation/recovery frame + authenticated account/credentials/users composition (`identity_*_shell`, public-state + denied partials) |
| **v0.6.0** | **v0.3.25** | **v0.4.5** | Identity lifecycle path/navigation contract (`PlatformPaths` + opt-in account/credentials/users/invite slots; reverse-proxy `root`) |
| **v0.5.24** | **v0.3.25** | **v0.4.5** | Accessible brand/home link in the bare login/passkey shell header |
| **v0.5.23** | **v0.3.25** | **v0.4.5** | Warm paper light palette across landing and product shells; dark theme precedence preserved; shared progressive landing frame |
| **v0.5.22** | **v0.3.24** | **v0.4.5** | Theme-aware public landing frame with bundled progressive-reveal assets; signed-in identity/avatar remains in the product sidebar foot |
| **v0.5.21** | **v0.3.24** | **v0.4.5** | Signed-in identity/avatar in the product sidebar foot; theme/locale remain in the header |
| **v0.5.20** | **v0.3.24** | **v0.4.5** | Basecoat product header with mobile sidebar trigger; passkey phone/QR entry and registration link |
| v0.5.19 | v0.3.23 | v0.4.5 | Material Symbols Outlined v364 bundled under same-origin `/static/platform`; profile validation failures return HTTP 400; hard in-bundle no-npm contract |
| v0.5.18 | v0.3.23 | v0.4.5 | Profile validation failures return HTTP 400; hard in-bundle no-npm contract (Basecoat + Tailwind safelist + layout keep-list + MANIFEST integrity/size) |
| v0.5.17 | v0.3.23 | v0.4.3 | Basecoat-first contract docs; CSS keep-list; chrome spacing + LAN storybook; drop dead `factory-*` aliases |
| v0.5.16 | v0.3.23 | v0.4.3 | Session card layout (#10) |
| v0.5.15 | v0.3.23 | v0.4.3 | interim pin (see git history) |
| v0.5.14 | v0.3.23 | v0.4.3 | interim pin (see git history) |
| v0.5.13 | v0.3.23 | v0.4.3 | Reliable server/client light-dark state sync; hide locale picker when only one locale is configured |
| v0.5.12 | v0.3.23 | v0.4.3 | Signed-in identity + deterministic accessible avatar in product header; guest-only sidebar foot |
| v0.5.11 | v0.3.23 | v0.4.3 | Passkey login/register **de** (DE) copy in my-auth; default locales pl/en/de |
| v0.5.10 | v0.3.19 | v0.4.3 | Locale flag **dropdown** (single select); theme single-fire |
| v0.5.9 | v0.3.17 | v0.4.3 | Theme toggle single handler (no double-fire); default shell header theme/locale; flag labels for locales |
| v0.5.8 | v0.3.16 | v0.4.3 | BOM stamp for mandatory username + product_shell; hosts pin equal tags |
| v0.5.7 | v0.3.13 | v0.3.3 | product_shell frame; compact html theme attrs |
| v0.5.6 | v0.3.12 | v0.3.3 | Full `product_shell` frame (sidebar+header+#main-content); hosts `extends` + menu data only |
| v0.5.5 | v0.3.11 | v0.3.3 | Shared `shell_boot.html` (`window.appShellConfig`); my-auth nested pin also on app-factory v0.5.5 |
| v0.5.4 | v0.3.10 | v0.3.3 | Host shell hooks on usermanager (`environment`, `base_template`, labels/`page_context`) |
| v0.5.4 | v0.3.10 | v0.3.2 | Grouped HTMX sidebar (`MenuGroup`) + Alpine afterSwap reinit in head_assets |
| v0.5.3 | v0.3.9 | v0.3.2 | Header theme/locale; foot Login/Account; **Log out only on account page** |
| v0.5.2 | v0.3.8 | v0.3.1 | Header theme/locale; foot had logout (superseded) |
| v0.5.1 | v0.3.7 | v0.3.1 | All chrome in platform foot (superseded) |
| v0.5.0 | v0.3.6 | v0.3.1 | Platform composition + product shell foot |

## Host rule

Prefer:

```toml
dependencies = ["app-factory[platform]"]
app-factory = { git = "https://github.com/mikolaj92/app-factory", tag = "v0.6.1" }
```

Do **not** float `my-usermanager` on `branch = "main"` for production hosts.
Do **not** re-copy theme boot, shell boot, or platform foot templates into hosts.

### Chrome placement (hosts must not fork)

| Surface | Partial | Contents |
|---------|---------|----------|
| **Main header** | `product_shell` + `platform_theme_locale` | language (optional) + icon theme toggle |
| **Sidebar foot** | `platform_auth` | signed-in identity/avatar, or guest Login (+ Register) |
| **Identity nav slot** | `platform_sidebar` (`data-platform-identity-navigation`) | opt-in Account / Credentials / Users / Invite (admin gated) |
| **Account page** | `platform_session` | **Log out** form (only place) |
| **Public activation/recovery** | `identity_public_shell` | branded no-sidebar frame; theme/locale; host notice/footer blocks |
| **Authenticated account/users** | `identity_authenticated_shell` | thin `product_shell` wrapper for adapter `base_template` / credential pages |
| **Invalid public capability** | `identity_public_state` | non-enumerating alert; host-overridable copy |
| **Unauthorized authenticated** | `identity_denied` / `identity_denied_fragment` | full-page shell or HTMX fragment |
| **No-sidebar shells** | `platform_controls` | theme/locale + auth (still no logout — include `platform_session` on the account/home surface) |

### Identity lifecycle paths

`PlatformPaths` is the shared route contract. Defaults match my-auth / my-usermanager:

| Surface | Default | Visibility |
|---------|---------|------------|
| login / logout / register | `/login`, `/logout`, `/register` | public |
| activation / recovery | `/activate`, `/recover` | public (capability URLs; not chrome links) |
| account / credentials | `/account`, `/account/passkeys` | authenticated |
| users / invite | `/admin/users`, `/admin/users/invite` | admin (`PlatformUser.is_admin`) |

Hosts may override every path and set `PlatformPaths.root` (e.g. `/argus`) for a reverse-proxy mount. `build_platform_context` resolves rooted URLs once. Enable sidebar links with `enable_account`, `enable_credentials`, `enable_admin_users`, and `enable_invite`. Adapters still own handlers; app-factory composes links, navigation, and shared shells.

Mount recipe:

- my-auth activation/recovery → extend `app_factory/identity_public_shell.html` (fill `identity_panel`, or override `content` for passkey centering).
- my-auth credentials / my-usermanager account & users → `base_template="app_factory/identity_authenticated_shell.html"` (or extend it).
- Invalid/expired capability → include `app_factory/identity_public_state.html`.
- Unauthorized GET → render `app_factory/identity_denied.html`; HTMX/mutations → include `identity_denied_fragment.html`.

Forbidden host forks: identity/avatar in the header, theme in sidebar, logout in nav menu, logout next to the account name, or host-owned activation/recovery/account chrome that duplicates these shells.
