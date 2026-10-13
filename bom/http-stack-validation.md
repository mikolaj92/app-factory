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
Branch protection requirements require authentication (public API returned 401).
No credentials were accessed. Remote CI for the follow-up starting SHA is
recorded below; it is not evidence for the new final SHA.

Integration: locally verified in the reference host only.
Publication: not performed; no newly released artifact was installed.
Other consumers: not changed or validated; only the in-repository reference
consumer was accessible within the permitted write scope.
Deployment: not performed; no service restart or deployed smoke is claimed.
Main integration: not performed; the production change is committed on the
requested current branch.

## PR #135 follow-up (2026-10-13 UTC)

Repository: `mikolaj92/app-factory`; PR: `135`; branch: `lokay/99`.
Starting SHA: `14ca1320554a629e3dbe5559dc57077ae978eab8`, clean tree.
Available `origin/main`: `7387a8112746edf1c25def581cb14d06f6d64f88`.
The follow-up final SHA is the commit containing this section; determine it with
`git log -1 --format=%H -- bom/http-stack-validation.md`.

Production file changed: `scripts/refresh_platform_assets.py`.
The report incorrectly accepted `2.0rc1` as current when PyPI's latest stable
release was `1.0`. An inline mocked command reproduced exit 0 (RED).
Exact version equality now rejects prerelease, development, yanked and unknown
newer locked versions. The same command then returned exit 1 (GREEN).
No new test files or functions were added, and existing assertions were retained.

The inline checks also confirmed current/stale reports (0/8 outdated), exclusion
of prerelease/dev/yanked releases, invalid JSON and metadata rejection, and
HTTP 503, network and timeout failures. Source failures raise an exception and
therefore cannot produce a successful CLI exit.

Independent live PyPI check: FastAPI 0.143.0, Starlette 1.8.0,
Uvicorn 0.54.0, HTTPX2 2.13.1; both locks current (8/8, exit 0).
Both locks passed `uv lock --check`; both frozen all-extras installations passed.
Separate root fastapi/platform/dev/browser and CI dev+browser installations
passed (5/5). Both environments use Python 3.14.3 in this follow-up.
The locked BOM tree contains HTTPX2/HTTPcore2, no legacy HTTP client or OpenAI.
No manifest or lock change was necessary.

| Actual cwd (under `/Users/mini-m4-0/Developer/app-factory/main-wt-99`) | Command | Starting-SHA result | Exit |
| --- | --- | --- | --- |
| `.` | `uv run --locked pytest -q` | 327 passed / 0 failed / 0 skipped | 0 |
| `examples/multi_user_bom` | `uv run --locked pytest -q` | 15 passed / 0 failed / 0 skipped | 0 |

Root Chromium installation, Ruff, release report and wheel/sdist build passed.
An inline transport probe passed responses, HTTP errors, injected timeout and
connection exceptions, explicit client close, asynchronous ASGITransport and
async close. Starlette TestClient's context ends the app lifespan but does not
set `is_closed`; explicit `close()` does. This is upstream behavior, not a
factory transport fallback. No product transport change was justified.

Public GitHub API confirmed PR #135's starting SHA and `pytest` success:
`https://github.com/mikolaj92/app-factory/actions/runs/38470384756/job/115547611601`.
That is **1/1 discovered checks for the starting SHA only**. Required checks
remain unknown because branch protection returned 401. Final-SHA remote CI is
not verified; this follow-up has not been pushed. No historical CI result closes
that boundary. Workflow commands propagate failures normally; no additional
workflow validation defect was demonstrated.

Final-SHA commands are rerun after the commit, with cwd, SHA, command, exit and
suite counts recorded in `.cache/validation/` locally. This ignored scratch
location is not a replacement for the committed evidence above.
No local gate implementation or `tested_cwds` collector exists in this repo.
Consequently, rerunning the external gate or clearing its two diagnostics is
not measurable here. Both actual test working directories are recorded above;
collector acceptance remains a separate evidence gap, not a product failure.

Main integration, publication, released-artifact consumer installation and
service deployment remain **not performed**. Nothing in this local validation
proves those actions.
