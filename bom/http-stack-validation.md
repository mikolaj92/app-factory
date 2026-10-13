# HTTP stack validation

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
