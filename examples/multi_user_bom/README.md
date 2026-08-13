# Multi-user platform BOM example

Reference FastAPI host pinned to the immutable multi-user compatibility BOM:

| Package | Tag |
|---------|-----|
| app-factory | `v0.6.3` (editable path while developing this repo) |
| my-auth | `v0.4.0` |
| my-usermanager | `v0.5.1` |

Machine-readable pins: [`bom/multi_user.toml`](../../bom/multi_user.toml).
Human matrix / upgrade order / migration: [`COMPAT.md`](../../COMPAT.md).

## Why `override-dependencies`?

`my-auth` and `my-usermanager` each declare nested `tool.uv.sources` for older
app-factory tags. Without a host override, `uv lock` fails with conflicting
URLs. This example (and production hosts) force one app-factory source:

```toml
[tool.uv]
override-dependencies = ["app-factory[platform]"]
```

## Run

```bash
cd examples/multi_user_bom
uv sync
uv run uvicorn app:app --reload --port 8770
```

Open http://127.0.0.1:8770 — switch between the seeded admin (2 passkeys) and
member (1 passkey), invite a user, and open activation/recovery capability URLs.

## Tests

```bash
cd examples/multi_user_bom
uv run pytest -q
```

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
app-factory = { git = "https://github.com/mikolaj92/app-factory", tag = "v0.6.3" }
my-auth = { git = "https://github.com/mikolaj92/my-auth", tag = "v0.4.0" }
my-usermanager = { git = "https://github.com/mikolaj92/my-usermanager", tag = "v0.5.1" }
```
