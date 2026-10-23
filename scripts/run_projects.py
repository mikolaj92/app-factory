#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = (ROOT, *(path.parent.resolve() for path in sorted((ROOT / "examples").glob("*/pyproject.toml"))))
PROJECT_TIMEOUT = 240  # Both suites must fit within Lokay's 600-second budget.


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project", choices=("root", "bom"),
        help="run one project for a separate CI step; default: run both",
    )
    args = parser.parse_args()
    projects = PROJECTS if args.project is None else (
        ROOT if args.project == "root" else ROOT / "examples" / "multi_user_bom",
    )
    failed = False
    results = []
    for project in projects:
        # Resolve from cwd and validate locks, including nested uv commands.
        # UV_ISOLATED overrides UV_PROJECT_ENVIRONMENT with a temporary environment.
        # Inherited pytest options can silently select tests or only collect them.
        # Source/group selectors can also disable the BOM's declared Git/path
        # sources or omit dependencies required by a complete suite.
        # An inherited config path can fail before pytest starts or replace
        # project settings; disabling config discovery also bypasses repo config.
        env = {
            key: value for key, value in os.environ.items()
            if key not in {
                "UV_WORKING_DIR", "UV_PROJECT", "UV_NO_PROJECT", "UV_NO_SYNC", "UV_FROZEN",
                "UV_ISOLATED", "UV_ENV_FILE", "PYTEST_ADDOPTS", "PLAYWRIGHT_BROWSERS_PATH",
                "UV_CONFIG_FILE", "UV_NO_CONFIG",
                "UV_NO_SOURCES", "UV_NO_SOURCES_PACKAGE",
                "UV_NO_DEV", "UV_NO_GROUP", "UV_NO_DEFAULT_GROUPS",
            }
        }
        # uv loads env files after this filtering and can restore pytest selectors.
        # Keep that bypass disabled for child and nested uv commands alike.
        env["UV_NO_ENV_FILE"] = "1"
        env["UV_PROJECT_ENVIRONMENT"] = str(project / ".venv")
        stages = [("SYNC", ["uv", "sync", "--locked", "--all-extras"])]
        if project == ROOT:
            stages.append((
                "BROWSER_INSTALL",
                ["uv", "run", "--locked", "--all-extras", "playwright", "install", "--with-deps", "chromium"],
            ))
        stages.append(("TEST", ["uv", "run", "--locked", "--all-extras", "pytest"]))
        for stage, argv in stages:
            print(f"LOKAY_{stage}_CWD={project}", flush=True)
            process = None
            try:
                process = subprocess.Popen(
                    argv, cwd=project,
                    env=env | {"PLAYWRIGHT_BROWSERS_PATH": str(ROOT / ".playwright")}
                    if stage == "BROWSER_INSTALL" else env,
                    start_new_session=os.name == "posix",
                )
                try:
                    returncode = process.wait(timeout=PROJECT_TIMEOUT)
                except BaseException:
                    if os.name == "posix":
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except OSError:
                            try:
                                process.kill()
                            except ProcessLookupError:
                                pass
                    else:
                        process.kill()
                    process.wait()
                    raise
            except subprocess.TimeoutExpired:
                print(f"{stage} timed out in {project} after {PROJECT_TIMEOUT}s", flush=True)
                returncode = 124
            except OSError as exc:
                print(f"Cannot run {stage} in {project}: {exc}", flush=True)
                returncode = 127
            print(f"LOKAY_{stage}_EXIT_CODE={returncode} cwd={project}", flush=True)
            result = {
                "argv": argv,
                "cwd": str(project),
                "pid": process.pid if process is not None else None,
                "returncode": returncode,
            }
            print(f"PROJECT_{stage}_RESULT=" + json.dumps(result), flush=True)
            results.append(result)
            failed |= returncode != 0
    print("PROJECT_CHECK_SUMMARY=" + json.dumps(results), flush=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
