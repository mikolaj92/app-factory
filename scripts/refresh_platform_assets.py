#!/usr/bin/env python3
"""
Deterministic maintainer script to refresh the local bundled platform assets.

Run from the repo root:

    python scripts/refresh_platform_assets.py

What it does:
- Uses scripts/platform_assets_src (package.json + lock) as the single source of truth.
- Runs `npm ci` from the committed lockfile.
- Runs the CSS build.
- Copies the 6 runtime files (CSS + 3 JS + Material Symbols CSS/font) into a staging directory.
- Copies and validates the Material Symbols Apache-2.0 license.
- Fetches real license texts from the exact upstream sources for the pinned versions.
- Validates that license content is non-empty and looks like a license (no 404/empty).
- Computes sha384 for all 6 bundled files.
- Writes a small MANIFEST.json inside the assets (for verification and for code to read).
- Replaces app_factory/assets with rollback protection.

This is the ONLY way new versions of the 6 files should enter the tree.
No ad-hoc curl in shell history. No manual copy.

After running, commit the changes to app_factory/assets/* and the lockfile if it changed.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SRC = REPO_ROOT / "scripts" / "platform_assets_src"
ASSETS_DST = REPO_ROOT / "app_factory" / "assets"
BASECOAT_LICENSE_FILENAME = "basecoat-css.LICENSE"
BASECOAT_VERSION = "1.0.2"
BASECOAT_REGISTRY_URL = f"https://registry.npmjs.org/basecoat-css/{BASECOAT_VERSION}"
BASECOAT_LICENSE_URL = (
    "https://raw.githubusercontent.com/hunvreus/basecoat/{git_head}/LICENSE.md"
)
MIT_REQUIRED_TEXT = (
    b"MIT License",
    b"Copyright",
    b"Permission is hereby granted, free of charge",
    b"The above copyright notice and this permission notice shall be included",
    b'THE SOFTWARE IS PROVIDED "AS IS"',
)
BASECOAT_REQUIRED_TEXT = MIT_REQUIRED_TEXT + (b"Copyright (c) 2025 Ronan Berder",)

CORE_FILES: dict[str, tuple[Path, str, str]] = {
    "basecoat-css": (
        BUILD_SRC / "dist" / "basecoat-factory.min.css",
        "basecoat-factory.min.css",
        "style",
    ),
    "basecoat-js-all": (
        BUILD_SRC / "node_modules" / "basecoat-css" / "dist" / "js" / "all.min.js",
        "basecoat-js.min.js",
        "script",
    ),
    "htmx": (
        BUILD_SRC / "node_modules" / "htmx.org" / "dist" / "htmx.min.js",
        "htmx.min.js",
        "script",
    ),
    "alpine": (
        BUILD_SRC / "node_modules" / "alpinejs" / "dist" / "cdn.min.js",
        "alpine.min.js",
        "script",
    ),
}
MATERIAL_SYMBOLS_VERSION = "v364"
MATERIAL_SYMBOLS_SOURCE_URL = (
    "https://fonts.gstatic.com/s/materialsymbolsoutlined/v364/"
    "kJF4BvYX7BgnkSrUwT8OhrdQw4oELdPIeeII9v6oDMzByHX9rA6RzaxHMPdY43zj-"
    "jCxv3fzvRNU22ZXGJpEpjC_1v-p5Y0J1Llf.woff2"
)
MATERIAL_SYMBOLS_FILES: dict[str, tuple[Path, str, str]] = {
    "material-symbols-css": (
        BUILD_SRC / "material-symbols" / "material-symbols.css",
        "material-symbols.css",
        "style",
    ),
    "material-symbols-font": (
        BUILD_SRC / "material-symbols" / "material-symbols-outlined.woff2",
        "material-symbols-outlined.woff2",
        "font",
    ),
}
MATERIAL_SYMBOLS_LICENSE_FILENAME = "material-symbols.LICENSE"
LANDING_VERSION = "1.0.0"
LANDING_FILES: dict[str, tuple[Path, str, str]] = {
    "landing-css": (ASSETS_DST / "landing.css", "landing.css", "style"),
    "landing-js": (ASSETS_DST / "landing.js", "landing.js", "script"),
}
BUNDLED_FILES: dict[str, tuple[Path, str, str]] = {
    **CORE_FILES,
    **MATERIAL_SYMBOLS_FILES,
    **LANDING_FILES,
}

LICENSE_SOURCES = {
    "htmx.LICENSE": (
        "htmx.org",
        "0BSD",
        "https://github.com/bigskysoftware/htmx",
        "https://raw.githubusercontent.com/bigskysoftware/htmx/v2.0.10/LICENSE",
    ),
    "alpine.LICENSE": (
        "alpinejs",
        "MIT",
        "https://github.com/alpinejs/alpine",
        "https://raw.githubusercontent.com/alpinejs/alpine/v3.17.1/LICENSE.md",
    ),
    "tailwindcss.LICENSE": (
        "tailwindcss (build-time; incorporated into generated CSS)",
        "MIT",
        "https://github.com/tailwindlabs/tailwindcss",
        "https://raw.githubusercontent.com/tailwindlabs/tailwindcss/v4.3.3/LICENSE",
    ),
}


def run(cmd: list[str], cwd: Path) -> None:
    print(f"+ {' '.join(cmd)} (cwd={cwd})")
    subprocess.run(cmd, cwd=cwd, check=True)


def b64sha384(path: Path) -> str:
    return "sha384-" + base64.b64encode(
        hashlib.sha384(path.read_bytes()).digest()
    ).decode("ascii")


def fetch_bytes(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:
        status = getattr(response, "status", None)
        if status != 200:
            raise HTTPError(url, int(status or 0), "bad status", response.headers, None)
        body = response.read()
    if not body or body.lstrip().lower().startswith((b"404", b"not found")):
        raise RuntimeError(f"invalid response body from {url}")
    return body


def validate_license(text: bytes, source: str, *, required: tuple[bytes, ...]) -> None:
    if len(text.strip()) <= 50 or any(marker not in text for marker in required):
        raise RuntimeError(f"invalid or incomplete license content from {source}")


def build_and_stage() -> Path:
    """Run the full build in the pinned sources and return a staging dir with final layout."""
    if not (BUILD_SRC / "package.json").exists():
        raise SystemExit(f"Missing {BUILD_SRC / 'package.json'}")

    # 1. npm ci (uses the committed lock)
    run(["npm", "ci"], cwd=BUILD_SRC)

    # 2. build CSS
    run(["npm", "run", "build:css"], cwd=BUILD_SRC)

    # 3. Prepare staging dir with the exact layout we ship in the package
    stage = Path(tempfile.mkdtemp(prefix="app-factory-assets-"))
    assets_stage = stage / "assets"
    assets_stage.mkdir()

    for source, filename, _kind in BUNDLED_FILES.values():
        if not source.is_file():
            raise RuntimeError(f"expected asset not found: {source}")
        shutil.copy2(source, assets_stage / filename)

    # 4. Licenses from exact sources + validation
    licenses_dir = assets_stage / "licenses"
    licenses_dir.mkdir()
    material_license = BUILD_SRC / "material-symbols" / MATERIAL_SYMBOLS_LICENSE_FILENAME
    if not material_license.is_file():
        raise RuntimeError(f"expected asset license not found: {material_license}")
    material_license_bytes = material_license.read_bytes()
    validate_license(
        material_license_bytes,
        str(material_license),
        required=(b"Apache License", b"TERMS AND CONDITIONS"),
    )
    shutil.copy2(material_license, licenses_dir / MATERIAL_SYMBOLS_LICENSE_FILENAME)

    for filename, (
        _package,
        license_name,
        _repository,
        source,
    ) in LICENSE_SOURCES.items():
        content = fetch_bytes(source)
        required = (
            MIT_REQUIRED_TEXT
            if license_name == "MIT"
            else (
                b"Permission to use, copy, modify, and/or distribute",
                b"THE SOFTWARE IS PROVIDED",
            )
        )
        validate_license(content, source, required=required)
        (licenses_dir / filename).write_bytes(content)

    package_json = json.loads(
        (BUILD_SRC / "node_modules" / "basecoat-css" / "package.json").read_text(
            encoding="utf-8"
        )
    )
    version = package_json.get("version")
    if version != BASECOAT_VERSION:
        raise RuntimeError(
            f"unreviewed basecoat-css version {version!r}; expected {BASECOAT_VERSION}"
        )
    if package_json.get("license") != "MIT":
        raise RuntimeError("basecoat-css package is not declared MIT")
    lock = json.loads((BUILD_SRC / "package-lock.json").read_text(encoding="utf-8"))
    lock_entry = lock.get("packages", {}).get("node_modules/basecoat-css", {})
    registry_metadata = json.loads(fetch_bytes(BASECOAT_REGISTRY_URL))
    registry_integrity = registry_metadata.get("dist", {}).get("integrity")
    if not isinstance(registry_integrity, str) or registry_integrity != lock_entry.get(
        "integrity"
    ):
        raise RuntimeError(
            "basecoat-css registry integrity does not match package-lock.json"
        )
    git_head = registry_metadata.get("gitHead")
    if not isinstance(git_head, str) or len(git_head) != 40:
        raise RuntimeError(
            "basecoat-css registry metadata has no authoritative gitHead"
        )
    license_source = BASECOAT_LICENSE_URL.format(git_head=git_head)
    basecoat_license = fetch_bytes(license_source)
    validate_license(basecoat_license, license_source, required=BASECOAT_REQUIRED_TEXT)
    (licenses_dir / BASECOAT_LICENSE_FILENAME).write_bytes(basecoat_license)

    # 5. Write manifest with versions + sha384 (for release verification)
    # Read versions from the build package.json or node_modules
    def read_version(package_name: str) -> str:
        package = json.loads(
            (BUILD_SRC / "node_modules" / package_name / "package.json").read_text(
                encoding="utf-8"
            )
        )
        version = package.get("version")
        if not isinstance(version, str) or not version:
            raise RuntimeError(f"invalid installed package version: {package_name}")
        return version

    manifest = {
        name: {
            "filename": filename,
            "version": (
                LANDING_VERSION
                if name in LANDING_FILES
                else MATERIAL_SYMBOLS_VERSION
                if name in MATERIAL_SYMBOLS_FILES
                else read_version(
                    "basecoat-css"
                    if name.startswith("basecoat-")
                    else "htmx.org"
                    if name == "htmx"
                    else "alpinejs"
                )
            ),
            "integrity": b64sha384(assets_stage / filename),
            "kind": kind,
        }
        for name, (_source, filename, kind) in BUNDLED_FILES.items()
    }

    (assets_stage / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    repository = package_json.get("repository")
    repository_url = repository.get("url") if isinstance(repository, dict) else None
    if not isinstance(repository_url, str) or not repository_url:
        raise RuntimeError("basecoat-css package has no repository URL")
    repository_directory = repository.get("directory")
    source = repository_url
    if isinstance(repository_directory, str) and repository_directory:
        source += f" ({repository_directory})"

    attribution = [
        "app-factory bundled platform assets",
        "",
        "Runtime/build provenance:",
    ]
    attribution.append(
        f"- basecoat-css {version}\n"
        f"  License: MIT\n"
        f"  Source: {source}\n"
        f"  Exact source commit: {git_head}\n"
        f"  Exact license: {license_source}\n"
        f"  License text: licenses/{BASECOAT_LICENSE_FILENAME}"
    )
    attribution.append(
        f"- Material Symbols Outlined {MATERIAL_SYMBOLS_VERSION}\n"
        "  License: Apache-2.0\n"
        f"  Source: {MATERIAL_SYMBOLS_SOURCE_URL}\n"
        f"  License text: licenses/{MATERIAL_SYMBOLS_LICENSE_FILENAME}"
    )

    for filename, (
        package,
        license_name,
        repository,
        source,
    ) in LICENSE_SOURCES.items():
        package_name = (
            "tailwindcss"
            if filename.startswith("tailwindcss")
            else "htmx.org"
            if filename.startswith("htmx")
            else "alpinejs"
        )
        attribution.append(
            f"- {package} {read_version(package_name)}\n"
            f"  License: {license_name}\n"
            f"  Source: {repository}\n"
            f"  Exact license: {source}\n"
            f"  License text: licenses/{filename}"
        )
    attribution.extend(("", "Runtime files:"))
    attribution.extend(
        f"- {name} {item['version']}: {item['filename']} ({item['integrity']})"
        for name, item in manifest.items()
    )
    (assets_stage / "ATTRIBUTION.txt").write_text(
        "\n".join(attribution) + "\n", encoding="utf-8"
    )

    return stage


def _exchange_directories(left: Path, right: Path) -> None:
    """Atomically exchange two directories or fail on unsupported platforms."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        exchange = libc.renameatx_np
        exchange.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        result = exchange(-2, os.fsencode(left), -2, os.fsencode(right), 0x00000002)
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        exchange = libc.renameat2
        exchange.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        result = exchange(-100, os.fsencode(left), -100, os.fsencode(right), 0x00000002)
    else:
        raise RuntimeError("atomic directory exchange is unsupported on this platform")
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), f"{left} <-> {right}")


def replace_assets(source: Path, destination: Path) -> None:
    """Replace the live tree with one atomic directory exchange."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    incoming = destination.with_name(
        f".{destination.name}.incoming-{os.urandom(4).hex()}"
    )
    shutil.copytree(source, incoming)
    try:
        if destination.exists():
            _exchange_directories(destination, incoming)
        else:
            os.replace(incoming, destination)
    finally:
        shutil.rmtree(incoming, ignore_errors=True)
    print(f"Replaced {destination} with new assets.")


def main() -> None:
    print("=== Refreshing local bundled platform assets ===")
    stage = build_and_stage()
    try:
        stage_assets = stage / "assets"
        required = {"MANIFEST.json", "ATTRIBUTION.txt"}
        required.update(filename for _, filename, _ in BUNDLED_FILES.values())
        required.add(f"licenses/{MATERIAL_SYMBOLS_LICENSE_FILENAME}")
        missing = [name for name in required if not (stage_assets / name).is_file()]
        if missing:
            raise RuntimeError(f"staging failed; missing: {missing}")
        replace_assets(stage_assets, ASSETS_DST)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    print("Done. Review and commit app_factory/assets and any lockfile change.")


if __name__ == "__main__":
    main()
