# HTTP stack validation

## Production runner repair from debd990

Repository: `mikolaj92/app-factory`, PR #135, branch `lokay/99`.
Baseline: `debd990d566dd61987a2881568aad0e77ab4d5aa`.
Repair revision: the commit introducing this section.
Verdict: **KEEP** until the host gate and required remote checks accept that SHA.

The baseline has no `scripts/test_projects.py`, although CI invokes it.
The visible baseline `pytest` check fails. The existing implementation from
`7c3d6d0` is now the sole runner, `scripts/run_projects.py`. Its production
filename avoids the reported `test_*.py` classification. Workflow and README
use the new path. Historical commands below describe earlier revisions only.
No test files, test functions, dependency pins or assertions changed.

Validation in `/Users/mini-m4-0/Developer/app-factory/main-wt-99`:

| Check | Result | Exit |
| --- | --- | --- |
| Runner with an intentionally different inherited environment | root 327 passed, 0 failed, 0 skipped; BOM 15 passed, 0 failed, 0 skipped | 0 |
| Lock checks and frozen all-extras installation | projects 2/2 | 0 each |
| Chromium installation with `--with-deps` | installed on macOS | 0 |
| Ruff | passed | 0 |
| Live stable-release check | current 8/8, outdated 0 | 0 |
| `uv build` | sdist and wheel built | 0 |

Both absolute cwd markers precede actual pytest summaries. The BOM cwd is
`/Users/mini-m4-0/Developer/app-factory/main-wt-99/examples/multi_user_bom`.
Each suite uses its own absolute `.venv`. Cache and browser installation stay
inside this checkout. The restored runner retains process-group termination
on POSIX, the 240-second timeout and nonzero failure propagation.

Local runner: projects **2/2**, locks **2/2**, omitted projects **0**.
These manual results do not establish host `tested_cwds` or selector acceptance.
Owner `mikolaj92`, tracking app-factory #99 / PR #135: select
`["uv", "run", "--locked", "python", "scripts/run_projects.py"]` in the
active host configuration and rerun the normal gate for the repair SHA.
Acceptance requires two recorded cwd paths and no missing-project findings.
A separate host task number remains unassigned; no host files were changed.
Active host classification, normal host build and selector remain unverified.

The public branch-protection endpoint returned HTTP 401 without authentication.
Required-check names and final-SHA remote CI therefore remain unverified.
No credentials were read, no push was performed, and no release or deployment
is claimed. The local package build is not the external Lokay build stage.

## Host-gate handoff and bounded runner

Verdict: **KEEP**, `mikolaj92/app-factory`, PR #135, branch `lokay/99`.
Baseline SHA: `c27cdfdbac9464f9e1eb8cbb19c9a86b232a18ef`.
The repair SHA is the commit introducing this section.

Read-only inspection found live PID 36303 executing
`/Users/mini-m4-0/.lokay/host/.venv/bin/lokay start`.
That host checkout has HEAD `64f37bfec76f138693ca259b4cc10e09f5394038`.
Its default configuration is `/Users/mini-m4-0/.lokay/host/repos.yaml`;
the app-factory entry selects `["uv", "run", "pytest"]`.
`LOKAY2_REPOS_FILE` can override that path. The process override was not
verified, so the default file is not asserted to be the effective source.
The saved run independently confirms the effective argv and baseline SHA:
`local_ci.result=red`, root-only `tested_cwds`, and two missing-BOM findings
for its manifest and lock. No saved state was edited.

The host path is `config.load_repos` → `start.resume` → `start._finish` →
`check.local_ci` → changed-package completeness checks in `start._finish`.
The interface passes one argv, not separate per-project commands.
`check.local_ci` already parses `LOKAY_TEST_CWD=` segments and requires a
successful nonempty test summary in every segment before recording cwd.
No new parser, pytest hook, second runner or fabricated marker is needed.
The existing host regression entry is
`/Users/mini-m4-0/.lokay/host/scenarios/ci_not_run.sh`.

Owner: `mikolaj92` (host configuration). Tracking context: app-factory #99 /
PR #135; a separate Lokay issue/PR number has **not been assigned**.
No host-maintenance command was verified. Handoff is recorded here, not
claimed as applied or delivered through an unverified maintenance mode.
The owner must identify the effective configuration (including any override),
change its app-factory test argv to
`["uv", "run", "--locked", "python", "scripts/run_projects.py"]`,
and ensure the next process loads that configuration. If a host code change
is needed, assign a Lokay task before editing it. Host and other checkouts
are outside this execution's permitted write scope.

Acceptance: the real gate for the repair SHA records root and
`examples/multi_user_bom`, reports no missing-project findings, and required
remote checks pass for that same SHA. Manual execution cannot satisfy this.
Do not repeat root-only autofix or change manifests to hide the missing cwd.

Concrete repository repair: the existing runner now uses `--locked`, so it
rejects stale manifests instead of accepting a frozen stale lock. Each child
has a 240-second timeout. Timeout, launch error, zero-test exit or any other
nonzero exit fails the runner; the other project still executes. Each child
retains its own absolute `.venv`, even with an inherited parent override.
No test files or functions were added or changed.

Validation of the repair before commit (both actual cwd paths as above):

| Command | Result | Exit |
| --- | --- | --- |
| `python3 scripts/test_projects.py` with deliberately different parent `UV_PROJECT_ENVIRONMENT` | root 327 passed, BOM 15 passed; 0 failed, 0 skipped | 0 |
| `uv lock --check` in each project | locks 2/2 | 0 each |
| `uv run --locked ruff check .` | passed | 0 |
| `uv run --locked python scripts/refresh_platform_assets.py --check-http-releases` | 8 current, 0 outdated | 0 |
| `uv build` | sdist and wheel built | 0 |
| `git ls-files --error-unmatch scripts/test_projects.py` | tracked | 0 |

Public GitHub API observation: baseline PR head and base are `c27cdfd` and
`7387a81`; its visible `pytest` check is successful (1/1). Required branch
protection checks were not verified. Final-SHA remote CI remains unverified.
Runner suites: 2/2. External gate: latest saved measurement 1/2 tested cwd,
1 omitted project. Integration, release and deployment remain unverified.

## CI repair from 999c122

Repository: `mikolaj92/app-factory`, PR #135, branch `lokay/99`.
Starting SHA: `999c122fe6e3b204a3aa066ca675ab443f16f28f`.
The repair revision is the commit introducing this section.

The starting commit deleted `scripts/test_projects.py`, but the workflow
still invoked it. Running `python3 scripts/test_projects.py` reproduced
exit 2: the file did not exist. Restore the existing runner without changing
workflow requirements, dependency pins or test assertions.

The runner executes both full suites from their actual project directories.
It overrides inherited `UV_PROJECT_ENVIRONMENT` with each project's absolute
`.venv` path. Each `LOKAY_TEST_CWD=` marker precedes a real pytest invocation.
Both suites run even if one fails; any nonzero exit or launch error fails the
runner. No unit test files or functions were added.

## Working-tree validation

Actual root: `/Users/mini-m4-0/Developer/app-factory/main-wt-99`.
BOM directory: `examples/multi_user_bom` under that root.
Python: 3.14.3 on macOS. Cache and Chromium downloads stay inside this checkout.
These results apply to the restored runner before committing, not remote CI.

| Directory | Command | Result | Exit |
| --- | --- | --- | --- |
| root | `uv lock --check` | valid | 0 |
| BOM | `uv lock --check` | valid | 0 |
| root | `uv sync --frozen --all-extras` | installed | 0 |
| BOM | `uv sync --frozen --all-extras` | installed | 0 |
| root | `uv run --locked playwright install chromium` | installed | 0 |
| root → BOM | `python3 scripts/test_projects.py` | 327 passed → 15 passed; no failures or skips | 0 |
| root | `uv run --locked ruff check .` | passed | 0 |
| root | `uv run --locked python scripts/refresh_platform_assets.py --check-http-releases` | 8 current, 0 outdated | 0 |
| root | `uv build` | sdist and wheel built | 0 |

Both projects were tested, not merely installed. No BOM manifest or lock change
was necessary to execute its existing 15 tests.

The live PyPI report confirms both locks contain FastAPI 0.143.0,
Starlette 1.8.0, Uvicorn 0.54.0 and HTTPX2 2.13.1 as current stable releases.
The BOM retains released my-auth v0.5.7 and my-usermanager v0.6.10 sources;
app-factory is the editable local checkout, not a newly published release.

## Evidence boundaries

Local suites: **2/2**. Valid locks: **2/2**.
Remote CI for the repair commit: **unverified**. Ubuntu/Python 3.12 execution
and required-check acceptance are not established by these macOS results.
The existing workflow now has its missing runner; its other checks remain intact.

External Lokay gate acceptance: **unverified**. No host configuration, host
checkout or saved gate results were changed. The host owner must select the
repo's two-project runner and rerun the real gate if it still selects root-only
pytest. Manual BOM execution does not prove external collector acceptance.

Main integration, publication, consumer upgrades and deployment:
**not performed**. No service restart or deployed smoke is claimed.
