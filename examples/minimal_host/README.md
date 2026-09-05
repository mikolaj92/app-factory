# Minimal chrome-only host

The shortest useful product host: one FastAPI app, one `PlatformConfig`, one
shared-shell template, no copied CSS/JS and no identity ceremony.

```bash
uv run uvicorn examples.minimal_host.app:app --reload
```

When identity is required, use `install_identity_adapters(...)` and the BOM in
`../multi_user_bom/`; do not grow this example into a second identity starter.
