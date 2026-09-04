# Multi-user platform BOM example

Reference FastAPI hosts pinned to the immutable multi-user compatibility BOM:

| Package | Tag |
|---------|-----|
| app-factory | `v0.6.27` (editable path while developing this repo) |
| my-auth | `v0.5.1` |
| my-usermanager | `v0.6.2` |

Machine-readable pins: [`bom/multi_user.toml`](../../bom/multi_user.toml).
Human matrix / upgrade order / migration: [`COMPAT.md`](../../COMPAT.md).

Two structurally different hosts share **one** installer
(`install_identity_adapters`):

| Host | Session | Paths | File |
|------|---------|-------|------|
| Cookie demo | raw cookie | defaults (`/login`, `/account`, …) | `app.py` |
| Portal demo | signed `SessionMiddleware` | `PlatformPaths.root="/portal"` | `rooted_app.py` |

Each host supplies only session transport, persistence, and the RBAC catalog.
Passkey ceremony stays in my-auth; user lifecycle stays in my-usermanager.

This generation uses my-auth packaged ceremony shells (no host
`my_auth_overrides`). SQLite hosts call `SQLiteAuthDatabase.initialize()` only —
do not follow it with `create_invitation_tables` or a dummy
`SQLiteEnrollmentCapabilityStore(db)` construction. Enrollment DDL
(`passkey_enrollment_capabilities`) is stamped by my-usermanager v0.6.2
`initialize()` via my-auth v0.5.1 `ensure_sqlite_schema`, including already-current schemas.

Chrome generation v0.6.21 / v0.5.1 / v0.5.7 had no composer — bump
app-factory to v0.6.27 (and UM to v0.6.2 if still on v0.5.7).

## Why `override-dependencies`?

`my-auth` and `my-usermanager` each declare nested `tool.uv.sources` for older
app-factory tags (UM v0.6.2 / my-auth v0.5.1 nest app-factory@v0.6.21). Without a host override, `uv lock` fails with conflicting
URLs. This example (and production hosts) force one app-factory source.
Do **not** override my-auth: UM v0.6.2 already nests my-auth@v0.5.1.

```toml
[tool.uv]
override-dependencies = ["app-factory[platform]"]
```

## Run

```bash
cd examples/multi_user_bom
uv sync
uv run uvicorn app:app --reload --port 8770
# rooted host: uv run uvicorn rooted_app:app --reload --port 8771
```

Open http://127.0.0.1:8770 — switch between the seeded admin (2 passkeys) and
member (1 passkey), invite a user, and open activation/recovery capability URLs.

## Tests

```bash
cd examples/multi_user_bom
uv run pytest -q
uv run ruff check app.py rooted_app.py policy.py tests
```

`tests/test_adapter_composition.py` runs the same installer against both hosts
and checks conflict / idempotency / fail-closed auth.

## Surfaces exercised

| Flow | Route | Owner |
|------|-------|-------|
| Bootstrap register | `/register` | my-auth |
| Invitation activation | `/activate?capability=…` | my-auth + my-usermanager |
| Account recovery | `/recover?capability=…` | my-auth |
| Credentials | `/account/passkeys` | my-auth on identity authenticated shell |
| Account | `/account` | my-usermanager on identity authenticated shell |
| Admin users | `/admin/users` | my-usermanager |
| Invite / reissue / revoke | `/admin/users` (POST `/admin/users/invite`) | my-usermanager packaged admin UI |

Rooted host serves the same surfaces under `/portal/…`.

## Production pin recipe

```toml
dependencies = [
  "app-factory[platform]",
  "my-auth[fastapi-htmx]",
  "my-usermanager[fastapi-htmx,myauth]",
]

[tool.uv]
override-dependencies = ["app-factory[platform]"]

[tool.uv.sources]
app-factory = { git = "https://github.com/mikolaj92/app-factory", tag = "v0.6.27" }
my-auth = { git = "https://github.com/mikolaj92/my-auth", tag = "v0.5.1" }
my-usermanager = { git = "https://github.com/mikolaj92/my-usermanager", tag = "v0.6.2" }
```
