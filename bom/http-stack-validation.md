# HTTP stack validation

Scope: `app-factory`, branch `lokay/99`, starting commit `7387a81`.
The starting checkout was clean and equal to the available `origin/main`.
This record belongs to the commit that adds it (`git log -1 -- bom/http-stack-validation.md`).
No other checkout, service configuration or GitHub credentials were accessed.

## Resolution

PyPI JSON independently confirmed the following stable releases during this change:

| Package | Version | Python requirement |
| --- | --- | --- |
| FastAPI | 0.143.0 | >=3.10 |
| Starlette | 1.8.0 | >=3.11 |
| Uvicorn | 0.54.0 | >=3.10 |
| HTTPX2 | 2.13.1 | >=3.10 |

Both projects resolved this combination. The library retains Python >=3.11;
the reference BOM host retains Python >=3.12.
The root lock is now committed rather than ignored.

The reference consumer retains released companion sources:

- my-auth v0.5.7: `bd0775f1993299b27d2bbd785dd252821dbff06e`.
- my-usermanager v0.6.10: `1844d41e0caad5a458a16bc16d3dcc54444b35fc`.
- app-factory: editable current checkout, **not a published release**.

`uv tree --locked --project examples/multi_user_bom` contains HTTPX2 and
HTTPcore2, with no HTTPX, requests or aiohttp. A source search found no legacy
HTTP imports, HTTPX2 aliases or client fallbacks in this repository.
FastAPI's optional `standard`/`all` and Starlette's optional `full` metadata still
mention HTTPX; these extras are not selected here. Consumers selecting them
must remove those extras or await upstream removal; this repository cannot
claim their dependency trees are clean.
OpenAI is absent, so no SDK change or SDK test applies.
Existing Pydantic DTO validation in `app_factory/runs.py` remains in place;
no demonstrated reduction justified another Pydantic dependency.

## Local evidence

| Check | Result |
| --- | --- |
| Projects / active locks | 2 / 2 |
| `uv lock --check` in both projects | 2 passed |
| Root extras, separately: fastapi, platform, dev, browser | 4 installations passed |
| Root dev + browser installation | passed |
| Full root suite, including both browser files | 327 passed, 0 failed, 0 skipped |
| BOM suite, run from its own directory | 15 passed, 0 failed, 0 skipped |
| `ruff check .` | passed |
| sdist + wheel build | passed |
| Fresh wheel installation with platform extra and import smoke | passed |
| Live release report | 8 current, 0 outdated, exit 0 |
| In-memory mocked stale release report | 8 outdated, exit 1 |
| Mocked prerelease and yanked versions | excluded |

The report validation used an ephemeral command, not a new test function or file.
Browser binaries and caches were kept inside this checkout.
Root validation used Python 3.11; BOM validation used Python 3.14.
Ubuntu / Python 3.12 CI has not been executed locally.
No type-check workflow exists; no new type-check configuration was invented.
No dedicated timeout/close regression functions were added under the user's
explicit restriction against new tests. Existing transport and adapter tests ran.

## Remaining evidence boundaries

The only checked-in CI job is `Tests / pytest`. It now checks both locks,
reports stable-release backlog using the existing refresh script, runs the
complete browser-enabled suite, lint, the BOM suite and package build.
Remote branch protection requirements were not read because authenticated
GitHub access is outside this execution. Final-SHA remote CI: **0 verified / 1
configured job**, not a failure verdict and not proof of branch requirements.

Integration: locally verified in the reference host only.
Publication: not performed; no newly released artifact was installed.
Other consumers: not changed or validated; only the in-repository reference
consumer was accessible within the permitted write scope.
Deployment: not performed; no service restart or deployed smoke is claimed.
Main integration: not performed; the production change is committed on the
requested current branch.
