import os
from pathlib import Path

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(
    Path(__file__).resolve().parent / ".playwright"
)
