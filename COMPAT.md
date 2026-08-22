# Platform BOM / compatibility matrix

Single source of truth for host pins when using `app-factory[platform]`.

Machine-readable multi-user BOM: [`bom/multi_user.toml`](bom/multi_user.toml).
Reference host: [`examples/multi_user_bom/`](examples/multi_user_bom/).

| app-factory | my-auth | my-usermanager | Contract |
|-------------|---------|----------------|----------|
| **v0.6.10** | **v0.4.5** | **v0.5.6** | **Identity-lifecycle plus shared HTMX/Alpine `file_upload` / `file_upload_field` and opt-in TAP `client_interactive`** (auth tags unchanged from v0.6.7; hosts configure `accept` / `max_bytes` / labels; no product format in the kit); keep my-auth 0.4.x (do not mix 0.5.x); hosts pin one immutable generation (see capability matrix) |
| **v0.6.7** | **v0.4.5** | **v0.5.6** | **Identity-lifecycle plus nested chrome aligned with TAP `client_shell`** (my-auth v0.4.5 and my-usermanager v0.5.6 nest app-factory v0.6.6; `SQLiteAuthDatabase.initialize()` stamps enrollment DDL on already-current schemas — hosts drop the second `ensure_sqlite_schema(conn)`); keep my-auth 0.4.x (do not mix 0.5.x); hosts pin one immutable generation (see capability matrix) |
| **v0.6.6** | **v0.4.2** | **v0.5.4** | **Identity-lifecycle plus slim TAP `client_shell` (no HTMX/Alpine) and `PlatformPaths.invite` default `/admin/users`** (additive on v0.6.5: enrollment capability DDL + nested my-auth pin in my-usermanager); keep my-auth 0.4.x (do not mix 0.5.x); hosts pin one immutable generation (see capability matrix) |
| **v0.6.5** | **v0.4.2** | **v0.5.4** | **Identity-lifecycle plus enrollment capability DDL** (my-auth v0.4.2 `ensure_sqlite_schema` stamps `passkey_enrollment_capabilities`; hosts drop dummy `SQLiteEnrollmentCapabilityStore(db)` after `initialize()`) **plus nested my-auth pin in my-usermanager** (v0.5.4 sources my-auth v0.4.2 + app-factory v0.6.4; hosts override `app-factory[platform]` only); keep my-auth 0.4.x (do not mix 0.5.x); hosts pin one immutable generation (see capability matrix) |
| **v0.6.4** | **v0.4.1** | **v0.5.2** | **Identity-lifecycle plus packaged ceremony shells** (my-auth v0.4.1 activation/recovery/credentials extend identity shells; hosts drop `my_auth_overrides`) **plus invitation DDL owned by SQLiteAuthDatabase** (my-usermanager v0.5.2 `initialize()` stamps `um_invitations`; hosts drop `create_invitation_tables`); keep my-auth 0.4.x (do not mix 0.5.x); hosts pin one immutable generation (see capability matrix) |
| **v0.6.3** | **v0.4.0** | **v0.5.1** | **Identity-lifecycle generation plus packaged invite admin** (status / reissue / revoke) from my-usermanager v0.5.1; keep my-auth v0.4.0 (do not mix 0.5.x); hosts pin one immutable generation (see capability matrix) |
| **v0.6.2** | **v0.4.0** | **v0.5.0** | **Multi-user identity-lifecycle BOM**: subject-bound enrollment/recovery + invitations + shared identity shells/paths; hosts pin one immutable generation (see capability matrix) |
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

Prefer the multi-user BOM generation (do not mix rows):

```toml
dependencies = [
  "app-factory[platform]",
  "my-auth[fastapi-htmx]",
  "my-usermanager[fastapi-htmx,myauth]",
]

[tool.uv]
# Nested adapter uv.sources still declare app-factory@v0.6.6
# (UM v0.5.6 / my-auth v0.4.5). Override app-factory only. Do not
# override my-auth — UM v0.5.6 already nests my-auth@v0.4.5.
override-dependencies = ["app-factory[platform]"]

[tool.uv.sources]
app-factory = { git = "https://github.com/mikolaj92/app-factory", tag = "v0.6.10" }
my-auth = { git = "https://github.com/mikolaj92/my-auth", tag = "v0.4.5" }
my-usermanager = { git = "https://github.com/mikolaj92/my-usermanager", tag = "v0.5.6" }
```

Do **not** float `my-usermanager` on `branch = "main"` for production hosts.
Do **not** re-copy theme boot, shell boot, or platform foot templates into hosts.
Do **not** mix BOM generations (for example app-factory v0.6.7 with my-auth v0.5.x).

### Identity lifecycle capability matrix (BOM v0.6.10)

| Capability | Owner | Default surface | Visibility |
|------------|-------|-----------------|------------|
| Bootstrap registration | my-auth | `/register` | public (host policy) |
| Invitation activation | my-auth + my-usermanager | `/activate` | public capability URL |
| Account recovery | my-auth | `/recover` | public capability URL |
| Account credentials | my-auth | `/account/passkeys` | authenticated |
| Account profile / session | my-usermanager | `/account` | authenticated |
| Admin user management | my-usermanager | `/admin/users` | admin |
| Invite issuance / reissue / revoke UI | my-usermanager | `/admin/users` (POST `/admin/users/invite`) | admin |
| Shared public / authenticated shells | app-factory | `identity_*_shell` | composition |
| Packaged ceremony shells | my-auth | `/activate`, `/recover`, `/account/passkeys` | composition |
| Invitation table DDL | my-usermanager | `SQLiteAuthDatabase.initialize()` | host bootstrap |
| Enrollment capability DDL | my-auth | `ensure_sqlite_schema` (via `SQLiteAuthDatabase.initialize()`) | host bootstrap |
| Path + identity nav contract | app-factory | `PlatformPaths` | composition |

### Supported upgrade order

Apply one generation at a time, in this order:

1. **app-factory** — paths (`PlatformPaths`) and identity shells (`v0.6.0` → `v0.6.10`).
2. **my-auth** — subject-bound enrollment / recovery plus packaged ceremony shells (`v0.4.5`); `ensure_sqlite_schema` stamps `passkey_enrollment_capabilities`; keep `PasskeyPaths` aligned with `PlatformPaths`. Do **not** mix my-auth `v0.5.x`.
3. **my-usermanager** — account lifecycle + packaged invite admin + invitation DDL in `SQLiteAuthDatabase.initialize()` (`v0.5.6`); nested sources my-auth v0.4.5 + app-factory v0.6.6; `initialize()` also stamps enrollment DDL on current auth schemas; set `base_template` to `app_factory/identity_authenticated_shell.html`.
4. **Host** — pin all three tags from the same BOM row, add `override-dependencies = ["app-factory[platform]"]` only (do not override my-auth), migrate templates (below), delete host-owned recovery/enrollment/invite chrome, drop `my_auth_overrides`, host `create_invitation_tables`, dummy `SQLiteEnrollmentCapabilityStore(db)` after `initialize()`, and the second host `ensure_sqlite_schema(conn)` call.

Rollback is the reverse order. Never run production with packages from different matrix rows.

### Migration from host-owned recovery / enrollment templates

1. Delete host copies of activation, recovery, enroll, and “set up passkey” full-page templates.
2. Point my-auth capability/credential pages at the shared shells. my-auth v0.4.5 packaged adapters already extend `identity_public_shell` / `identity_authenticated_shell`; delete host `my_auth_overrides` for those two templates. Login/register stay on `shell.html`.
3. Set `UserManagerUiConfig.base_template = "app_factory/identity_authenticated_shell.html"`.
4. Route invite delivery through my-usermanager `InvitationService` + my-auth enrollment capabilities; links target `platform_paths.activation` / `recovery` with the opaque token only.
5. Delete host `invite.html`. Implement `invite_user`, `reissue_invitation`, and `revoke_invitation` hooks so the packaged admin users UI owns issuance / reissue / revoke (activation URL is shown once after invite/reissue).
6. After `SQLiteAuthDatabase.initialize()`, do not call host `create_invitation_tables` — invitation DDL (`um_invitations`) is stamped in the same owned transaction (my-usermanager v0.5.2+). Do not construct a dummy `SQLiteEnrollmentCapabilityStore(db)` after `initialize()`, and do not call `ensure_sqlite_schema` a second time — enrollment DDL (`passkey_enrollment_capabilities`) is stamped by my-usermanager v0.5.6 `initialize()` via my-auth v0.4.5 `ensure_sqlite_schema` even when the auth schema is already current. Drop `my-auth` from `override-dependencies` if present (UM v0.5.6 nests v0.4.5).
7. Enable identity nav with `enable_account`, `enable_credentials`, `enable_admin_users`, `enable_invite` instead of hand-built sidebar entries.
8. Keep product authorization/role policy in the host; do not fork adapter ceremony markup.

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
| **Slim TAP client** | `client_shell` | Basecoat + theme boot + `platform_controls`; no HTMX/Alpine. Hosts extend this instead of forking `client_base.html` |

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
