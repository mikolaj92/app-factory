#!/usr/bin/env python3
"""Run both project suites with isolated environments and actual cwd markers.

Setup (including Chromium) remains a separate step. A marker is not proof of
success: each following pytest invocation must produce its own passing summary.
Each invocation checks its lock and has a bounded execution time.
"""

from __future__ import annotations

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
        # Resolve from cwd, including nested uv commands launched by the suite.
        env = {
            key: value for key, value in os.environ.items()
            if key not in {"UV_WORKING_DIR", "UV_PROJECT"}
        }
        env["UV_PROJECT_ENVIRONMENT"] = str(project / ".venv")
        argv = ["uv", "run", "--locked", "--all-extras", "pytest", "-q"]
        print(f"LOKAY_TEST_CWD={project}", flush=True)
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
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
                process.wait()
                raise
        except subprocess.TimeoutExpired:
            print(f"Tests timed out in {project} after {PROJECT_TIMEOUT}s", flush=True)
            failed = True
        except OSError as exc:
            print(f"Cannot run tests in {project}: {exc}", flush=True)
            failed = True
        else:
            failed |= returncode != 0
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
