# Multi-user platform BOM example

Reference FastAPI hosts use the multi-user compatibility BOM.
The factory source is a local editable path for development only.

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
(`passkey_enrollment_capabilities`) is stamped by `initialize()` via
my-auth `ensure_sqlite_schema`, including already-current schemas.

## Why `override-dependencies`?

`my-auth` and `my-usermanager` both nest app-factory v0.7.9.
Without a host override, `uv lock` fails with conflicting
URLs. This example (and production hosts) force one app-factory source.
Do **not** override my-auth: UM v0.6.10 nests my-auth@v0.5.7.

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

Production hosts use the immutable Git sources and tags from the BOM,
with the source recipe in [COMPAT.md](../../COMPAT.md#host-rule).
