#!/usr/bin/env python3
"""Run both project suites with isolated environments and actual cwd markers.

Setup (including Chromium) remains a separate step. A marker is not proof of
success: each following pytest invocation must produce its own passing summary.
Each invocation checks its lock and has a bounded execution time.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = (ROOT, ROOT / "examples" / "multi_user_bom")
PROJECT_TIMEOUT = 240  # Both suites must fit within Lokay's 600-second budget.


def main() -> int:
    failed = False
    for project in PROJECTS:
        env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(project / ".venv")}
        argv = ["uv", "run", "--locked", "--all-extras", "pytest", "-q"]
        print(f"LOKAY_TEST_CWD={project}", flush=True)
        try:
            result = subprocess.run(
                argv, cwd=project, env=env, check=False, timeout=PROJECT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            print(f"Tests timed out in {project} after {PROJECT_TIMEOUT}s", flush=True)
            failed = True
        except OSError as exc:
            print(f"Cannot run tests in {project}: {exc}", flush=True)
            failed = True
        else:
            failed |= result.returncode != 0
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
