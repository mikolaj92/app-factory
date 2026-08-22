# app-factory agent notes

## Scope

Shared **UI chrome / shell** for FastAPI + Jinja2 + HTMX + Alpine apps:
bundled same-origin assets, head/theme/shell boots, and small composable
Jinja partials (`product_shell`, platform nav/auth/session/theme, identity
frames). See `README.md` and `COMPAT.md`.

## Design law

**Prefer small modules.** Grow the package with focused partials and helpers,
not product workflows.

| Belongs here | Belongs in consumers |
|--------------|----------------------|
| Chrome frame, layout primitives, theme/locale/session glue | Domain routes, ORM, product CSS |
| Small composable shell / identity partials | Multi-step process flows and product workflows |
| HTMX redirects, session CSRF adapter, toast/error boot, pagination | Product RBAC, validation, routes, and copy |
| Bundled Basecoat/HTMX/Alpine + optional CDN pins | Ordering / orchestration (compose with **Fala** where applicable) |

Do **not** absorb host business logic, ceremony sequences, or Fala graphs into
this repo. Hosts extend the shell and compose product flows outside
app-factory.

## Hard bans

- **No** fat multi-step product wizards or workflow engines here.
- **No** re-implementing auth ceremony (that lives in my-auth / my-usermanager).
- **No** host-style domain models or product routes.
- **No** new `.app-*` components for things Basecoat already provides.
