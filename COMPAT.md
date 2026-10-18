# Platform BOM / compatibility matrix

Machine-readable multi-user pins: [`bom/multi_user.toml`](bom/multi_user.toml).
Reference host: [`examples/multi_user_bom/`](examples/multi_user_bom/).

| app-factory | my-auth | my-usermanager | Contract |
|-------------|---------|----------------|----------|
| **v0.7.9** | **v0.5.7** | **v0.6.10** | Lism 1.0.1 layout-only CSS with Basecoat components and Tailwind utilities. Shared views, passkey panels and account/admin forms use adaptive layouts. Columns follow container width. |

## Host rule

Pin all three packages together. Override only app-factory so nested adapter
sources resolve to one factory. Do not override my-auth or float production
sources on branches.

```toml
dependencies = [
  "app-factory[platform]",
  "my-auth[fastapi-htmx]",
  "my-usermanager[fastapi-htmx,myauth]",
]

[tool.uv]
override-dependencies = ["app-factory[platform]"]

[tool.uv.sources]
app-factory = { git = "https://github.com/mikolaj92/app-factory", tag = "v0.7.9" }
my-auth = { git = "https://github.com/mikolaj92/my-auth", tag = "v0.5.7" }
my-usermanager = { git = "https://github.com/mikolaj92/my-usermanager", tag = "v0.6.10" }
```

### Supported upgrade order

The compatible target is `v0.7.9` / `v0.5.7` / `v0.6.10`.

1. Align factory paths (`PlatformPaths`), shared identity shells and `install_identity_adapters` composition.
2. Align my-auth subject-bound enrollment/recovery and `PasskeyPaths` with factory paths.
3. Initialize my-usermanager through `SQLiteAuthDatabase.initialize()`; it also stamps invitation and enrollment DDL.
4. Pin the complete row with `override-dependencies = ["app-factory[platform]"]`, regenerate the host lock and run its full checks.

Before migrating older auth, verify database backup restoration in an isolated
sandbox with separate sessions and no real invitation delivery. Reverting pins
does not revert data migrations; restore compatible data as well.

### Migration from host installer forks (`install_identity_adapters`)

Use **v0.7.9 / v0.5.7 / v0.6.10** with the composer shown in the
[README](README.md#passkey-login-my-auth--this-package).

Delete host calls to `install_passkey_ui` / `install_usermanager_ui`, their UI
config construction, dummy render hooks, manual path copying and chrome-global
rebinding. The composer supplies shared shells and paths. Remove copied
recovery/enrollment/invite templates and `my_auth_overrides`.

Keep persistence, session transport, authorization, role/capability catalogs,
invitation delivery and optional product `page_context` in the host.
After `SQLiteAuthDatabase.initialize()`, do not call `create_invitation_tables`,
construct a dummy `SQLiteEnrollmentCapabilityStore(db)`, or repeat
`ensure_sqlite_schema(conn)`.

For signed sessions, add `SessionMiddleware` after composition and supply
`SessionCsrfProtection()` in the bindings. Starlette runs last-added middleware
first. Admin UI without CSRF and a passkey service without hooks fail closed.
Identical installation is idempotent; changed mounts, config or adapter selection
raise `IdentityAdapterConflict`.

### Identity lifecycle paths

`PlatformPaths` defines the shared route contract. Adapters own the handlers.

| Surface | Default | Visibility |
|---------|---------|------------|
| login / logout / register | `/login`, `/logout`, `/register` | host registration policy; logout requires a session |
| activation / recovery | `/activate`, `/recover` | public capability URLs |
| account / credentials | `/account`, `/account/passkeys` | authenticated |
| users / invite | `/admin/users` | admin (`PlatformUser.is_admin`) |

Invite issuance posts to `/admin/users/invite`; reissue/revoke use the packaged
admin UI. InvitationService and auth enrollment capabilities own this lifecycle.
The activation URL appears once after invite/reissue; hosts supply delivery policy.

Override paths and set `PlatformPaths.root` for a route prefix.
`build_platform_context` resolves rooted URLs once. Enable navigation with
`enable_account`, `enable_credentials`, `enable_admin_users` and `enable_invite`.
Activation/recovery URLs carry opaque capabilities and are not sidebar links.

### Chrome placement

| Surface | Owner |
|---------|-------|
| Main header | `product_shell` + `platform_theme_locale`: locale and theme |
| Sidebar foot | `platform_auth`: identity/avatar or guest login/register |
| Identity navigation | `platform_sidebar`: enabled account/credentials/admin links |
| Account logout form | `platform_session`; not the header or navigation |
| Public activation/recovery | `identity_public_shell`: brand, theme/locale, notice/footer slots |
| Account/credentials/users | `identity_authenticated_shell`; loads usermanager CSS when `static_url_path` is set |
| Invalid/expired capability | `identity_public_state`: non-enumerating alert |
| Unauthorized response | `identity_denied` full page or `identity_denied_fragment` for HTMX |
| Slim client | `client_shell`: Basecoat/theme/auth without HTMX/Alpine; `client_interactive` opts in |

Do not copy theme boot, shell boot or identity templates into hosts.
New content/form layouts use Lism primitives; Basecoat owns component anatomy
and padding. One container has one layout owner. Legacy `.app-*` layouts remain
compatible; do not combine them with competing Lism layout classes.
