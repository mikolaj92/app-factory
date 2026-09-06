"""Local untracked helpers must not hide a broken CI checkout (PR #85)."""

from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_product_bootstrap_imports_from_tracked_package_only(tmp_path: Path) -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "app_factory"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode().split("\0")
    for name in filter(None, tracked):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)

    # Isolate the source tree while retaining installed FastAPI dependencies.
    # A regular package loaded here cannot find untracked helpers in ROOT.
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from app_factory import ProductAppConfig, create_product_app; "
            "assert callable(create_product_app); "
            "app = create_product_app(ProductAppConfig()); "
            "assert app.state.app_factory_product.environment is not None",
            str(tmp_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
