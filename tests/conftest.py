import os
from pathlib import Path

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    str(Path(__file__).resolve().parents[1] / ".runtime" / "ms-playwright"),
)
