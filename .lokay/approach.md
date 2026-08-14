# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/app-factory issue=43 -->

Repository: `mikolaj92/app-factory`  
Issue: #43 — Nagłówek README nadal Bundled core assets v0.5.19 przy tagu v0.6.5

## Goal

README L73: „Bundled core assets (\`v0.5.19\`)”. Tag produktu: v0.6.5. Plik `app_factory/assets/basecoat-factory.min.css` jest.

## Files likely touched

- `README.md` (heading `## Bundled core assets (`v0.5.19`)` → current product tag `v0.6.5`)

## Test plan

- `uv run pytest tests/test_fastapi.py::test_runtime_version_matches_project_metadata tests/test_shared_pin_contract.py tests/test_cdn.py::test_core_assets_are_local_and_manifest_verified -q`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
