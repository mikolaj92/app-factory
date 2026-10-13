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

## Validation handoff: separate setup and tests

Repository `mikolaj92/app-factory`, PR `135`, branch `lokay/99`.
Starting SHA: `6abc649834f8eea963a602b30e1be0af5c6185e1`, clean tree.
SSH `git ls-remote` confirmed `origin/main` remains
`7387a8112746edf1c25def581cb14d06f6d64f88`; no fetch or branch change was needed.
The final SHA is the commit introducing this section.

### Confirmed external gate defect (KEEP)

Read-only evidence: `/Users/mini-m4-0/.lokay/runs/mikolaj92__app-factory/99/state.json`
records setup in both directories, but only `uv run pytest` at the root.
It records `326 passed / 0 failed / 1 skipped`, `tested_cwds` containing only
root, and both missing-BOM-test diagnostics. This is **1/2**, not 2/2.
The BOM suite was not executed by that gate; its proof was not merely lost.

Owner: Lokay host. Exact implementation paths:

- `/Users/mini-m4-0/.lokay/host/src/lokay/config.py:load_repos` reads one repo test argv.
- `/Users/mini-m4-0/.lokay/host/src/lokay/setup.py:prepare_dependencies` installs nested projects.
- `/Users/mini-m4-0/.lokay/host/src/lokay/start.py:1032` passes only that argv to `local_ci` at root.
- `/Users/mini-m4-0/.lokay/host/src/lokay/check.py:local_ci` records successful test cwd,
  or actual `LOKAY_TEST_CWD=` markers; setup is not counted.
- `/Users/mini-m4-0/.lokay/host/src/lokay/start.py:1039–1050` checks changed nested manifests against those cwd values.

These files are outside the permitted write scope. They were not changed.
No repo-side manifest edit can repair the host's command selection. The gate
has not been rerun or cleared here. Required host regressions remain blocked
by the write boundary; no synthetic cwd was added to its state.

### Concrete repository change

`.github/workflows/tests.yml` now has explicit, separately named lock, setup
and test steps for both projects. BOM setup uses its actual working directory;
previously it was implicit in `uv run`. Root setup now validates all public
extras, rather than dev/browser only. Errors still stop the job. README now
includes the full two-project commands and all three browser files.
No tests, manifests, pins or locks needed changes.

The review at `examples/multi_user_bom/pyproject.toml:7–18` supplied no concrete
input or expected failure. Independent lock check, frozen install and all
15 BOM tests pass. The manifest keeps released auth/UM tags and the editable
factory override; no reproducible dependency or validation defect was found.

An inherited `UV_PROJECT_ENVIRONMENT` pointed both manual commands at the
root environment. Reproduction: BOM sync removed root Playwright; root
`uv run --locked playwright ...` then exited 2. Per-project absolute values
restored separate environments. This is a harness environment condition,
not justification for changing the BOM dependencies. Manual validation used
`UV_PROJECT_ENVIRONMENT=<actual cwd>/.venv`, `UV_CACHE_DIR=<root>/.cache/uv`
and `PLAYWRIGHT_BROWSERS_PATH=<root>/.cache/ms-playwright`.
All generated validation files and browsers stay in this checkout.

### Fresh local results (working tree before commit)

| Actual cwd | Check | Passed / failed / skipped | Exit |
| --- | --- | --- | --- |
| root | `uv lock --check` | lock valid | 0 |
| BOM | `uv lock --check` | lock valid | 0 |
| root | `uv sync --frozen --all-extras` | installed | 0 |
| BOM | `uv sync --frozen --all-extras` | installed | 0 |
| root | `uv run --locked playwright install --with-deps chromium` | installed | 0 |
| root | `uv run --locked pytest -q` | 327 / 0 / 0 | 0 |
| BOM | `uv run --locked pytest -q` | 15 / 0 / 0 | 0 |
| root | `uv run --locked ruff check .` | passed | 0 |
| root | `uv run --locked python scripts/refresh_platform_assets.py --check-http-releases` | 8 current / 0 outdated | 0 |
| root | `uv build` | wheel + sdist built | 0 |

PyPI independently confirms FastAPI 0.143.0, Starlette 1.8.0, Uvicorn 0.54.0,
HTTPX2 2.13.1. Own-code import search found HTTPX2 only, no aliases, legacy
fallbacks or OpenAI. Historical upstream optional-extra boundaries still apply.
Final-SHA validation is stored separately under `.cache/validation/` with
repo, PR, SHA, cwd, argv, exit and log; it is manual evidence, not Lokay acceptance.

### Remote and release boundaries

Unauthenticated public API confirms one successful discovered check on the
**starting SHA only**:
<https://github.com/mikolaj92/app-factory/actions/runs/38472797378/job/115555915374>.
Branch protection returned HTTP 401, so required-check total is unknown.
No GitHub token was read or written. This new commit has not been pushed;
final-SHA required CI is **unverified (0 verified / unknown total)**.
Local gate: **1/2 recorded, KEEP**. Manual suites: **2/2**. Locks: **2/2**.
Main integration, publication and deployment: **not performed**, separately.
