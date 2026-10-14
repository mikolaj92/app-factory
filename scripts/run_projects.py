#!/usr/bin/env python3
"""Run both project suites with isolated environments and actual cwd markers.

Setup (including Chromium) remains a separate step. A marker is not proof of
success: each following pytest invocation must produce its own passing summary.
Each invocation checks its lock and has a bounded execution time.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = (ROOT, ROOT / "examples" / "multi_user_bom")
PROJECT_TIMEOUT = 240  # Both suites must fit within Lokay's 600-second budget.


def main() -> int:
    failed = False
    for project in PROJECTS:
        # Resolve from cwd and validate locks, including nested uv commands.
        # UV_ISOLATED overrides UV_PROJECT_ENVIRONMENT with a temporary environment.
        # Inherited pytest options can silently select tests or only collect them.
        env = {
            key: value for key, value in os.environ.items()
            if key not in {
                "UV_WORKING_DIR", "UV_PROJECT", "UV_NO_PROJECT", "UV_NO_SYNC", "UV_FROZEN",
                "UV_ISOLATED", "UV_ENV_FILE", "PYTEST_ADDOPTS",
            }
        }
        # uv loads env files after this filtering and can restore pytest selectors.
        # Keep that bypass disabled for child and nested uv commands alike.
        env["UV_NO_ENV_FILE"] = "1"
        env["UV_PROJECT_ENVIRONMENT"] = str(project / ".venv")
        argv = ["uv", "run", "--locked", "--all-extras", "pytest", "-q"]
        print(f"LOKAY_TEST_CWD={project}", flush=True)
        process = None
        try:
            process = subprocess.Popen(
                argv, cwd=project, env=env, start_new_session=os.name == "posix",
            )
            try:
                returncode = process.wait(timeout=PROJECT_TIMEOUT)
            except BaseException:
                # uv launches pytest, which can launch browser/server children.
                # Kill the entire session before starting the other project.
                if os.name == "posix":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except OSError:
                        # A missing group does not prove that uv has exited.
                        # If group signalling fails, still stop and reap uv.
                        try:
                            process.kill()
                        except ProcessLookupError:
                            pass
                else:
                    process.kill()
                process.wait()
                raise
        except subprocess.TimeoutExpired:
            print(f"Tests timed out in {project} after {PROJECT_TIMEOUT}s", flush=True)
            returncode = 124
        except OSError as exc:
            print(f"Cannot run tests in {project}: {exc}", flush=True)
            returncode = 127
        # Report actual child status; 124/127 identify timeout/launch failures.
        # This complements, never replaces, the real pytest summary above.
        print(f"LOKAY_TEST_EXIT_CODE={returncode} cwd={project}", flush=True)
        # A launch request or cwd marker alone is not execution evidence.
        print("PROJECT_TEST_RESULT=" + json.dumps({
            "argv": argv,
            "cwd": str(project),
            "pid": process.pid if process is not None else None,
            "returncode": returncode,
        }), flush=True)
        failed |= returncode != 0
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
