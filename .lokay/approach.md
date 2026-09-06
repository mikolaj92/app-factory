# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/app-factory issue=83 -->

Repository: `mikolaj92/app-factory`  
Issue: #83 — Wspólna prezentacja rezultatów i bezpieczne pobieranie artefaktów

## Goal

Dostarczyć domenowo neutralny result panel oraz download route dla typed artifact references po terminalnym runie.

## Files likely touched

- `app_factory/runs.py` — `RunArtifact` metadata, `RunResult`, `RunArtifactStream`, `RunPort.get_result` / `open_artifact`
- `app_factory/run_routes.py` — result panel on terminal success + authorized download route
- `app_factory/__init__.py` — public exports
- `app_factory/templates/app_factory/components/run_results.html` — values/links/downloads
- `app_factory/templates/app_factory/components/run_detail.html` — include results fragment
- `tests/test_runs.py` — presentation, authz, filename, digest mismatch

## Test plan

- Lokalny plik, external URL i metadata-only result mają osobne poprawne prezentacje.
- Użytkownik bez authority nie może pobrać artifactu znając ID.
- Filename nie pozwala wyjść poza storage ani wstrzyknąć headera.
- Digest mismatch failuje i jest widoczny.
- Widok działa jako fragment HTMX i pełna strona.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and lokay must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
