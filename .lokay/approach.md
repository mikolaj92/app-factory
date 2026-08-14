# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/app-factory issue=41 -->

Repository: `mikolaj92/app-factory`  
Issue: #41 — Brak powłoki bez HTMX/Alpine — hosty forkują

## Goal

Argus `client_base.html` ręcznie składa dokument (theme_boot + platform_controls + platform_session), bo `shell.html` zawsze ciągnie HTMX/Alpine z `head_assets`. Ścieżka klienta TAP ma być slim Basecoat.

## Files likely touched

- `app_factory/templates/app_factory/client_shell.html` (new slim TAP document)
- `app_factory/templates/app_factory/head_assets_slim.html` (Basecoat/icons only)
- `app_factory/templates/app_factory/head_assets.html` (reuse slim + HTMX/Alpine)
- `app_factory/templates/app_factory/shell.html` (`head_assets` block)
- `app_factory/platform.py` / `app_factory/__init__.py` (`CLIENT_SHELL`)
- `example/app.py` + `example/templates/stories/client.html`
- `tests/test_identity_shells.py`, `tests/test_example_storybook.py`, `tests/test_cdn.py`, `tests/test_fastapi.py`
- `README.md`, `COMPAT.md`

## Test plan

- `uv run pytest tests/test_identity_shells.py tests/test_example_storybook.py tests/test_cdn.py tests/test_fastapi.py tests/test_platform.py -q`

## Non-goals

- BOM pin changes
- Removing HTMX/Alpine from operator `shell.html` / `product_shell`

## Notes

- Kit ships `client_shell` so TAP hosts extend it instead of forking `client_base.html`.
- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
