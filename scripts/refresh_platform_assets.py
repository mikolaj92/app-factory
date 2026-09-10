#!/usr/bin/env python3
"""
Deterministic maintainer script to refresh the local bundled platform assets.

Run from the repo root:

    python scripts/refresh_platform_assets.py

What it does:
- Fetches HTMX minified dist from the pinned GitHub tag (no npm).
- Fetches Alpine, Basecoat, and the Tailwind browser engine from pinned npm
  tarballs (integrity-checked; no package lock and no local install).
- Concatenates Basecoat's published CDN CSS with factory `.app-*` layout and
  the warm-paper palette. Arbitrary Tailwind utilities come from the bundled
  browser engine at runtime — hosts never install npm.
- Copies landing extras into a staging directory.
- Fetches real license texts from the exact upstream sources for the pinned versions.
- Validates that license content is non-empty and looks like a license (no 404/empty).
- Computes sha384 for all bundled files.
- Writes a small MANIFEST.json inside the assets (for verification and for code to read).
- Replaces app_factory/assets with rollback protection.

This is the ONLY way new versions of the bundled files should enter the tree.
No ad-hoc curl in shell history. No manual copy.

After running, commit the changes to app_factory/assets/*.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import io
import json
import os
import shutil
import sys
import tarfile
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
BASECOAT_CDN_CSS_PATH = "package/dist/basecoat.cdn.min.css"
BASECOAT_JS_PATH = "package/dist/js/all.min.js"
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

HTMX_VERSION = "4.0.0"
HTMX_FILENAME = "htmx.min.js"
HTMX_SOURCE_URL = (
    "https://raw.githubusercontent.com/bigskysoftware/htmx/"
    f"v{HTMX_VERSION}/dist/htmx.min.js"
)
HTMX_LICENSE_URL = (
    f"https://raw.githubusercontent.com/bigskysoftware/htmx/v{HTMX_VERSION}/LICENSE"
)
ALPINE_VERSION = "3.17.2"
ALPINE_FILENAME = "alpine.min.js"
ALPINE_REGISTRY_URL = f"https://registry.npmjs.org/alpinejs/{ALPINE_VERSION}"
ALPINE_DIST_PATH = "package/dist/cdn.min.js"
ALPINE_LICENSE_URL = (
    f"https://raw.githubusercontent.com/alpinejs/alpine/v{ALPINE_VERSION}/LICENSE.md"
)
TAILWIND_BROWSER_VERSION = "4.3.3"
TAILWIND_BROWSER_FILENAME = "tailwind.min.js"
TAILWIND_BROWSER_REGISTRY_URL = (
    f"https://registry.npmjs.org/@tailwindcss/browser/{TAILWIND_BROWSER_VERSION}"
)
TAILWIND_BROWSER_DIST_PATH = "package/dist/index.global.js"
TAILWIND_LICENSE_URL = (
    "https://raw.githubusercontent.com/tailwindlabs/tailwindcss/"
    f"v{TAILWIND_BROWSER_VERSION}/LICENSE"
)
CORE_FILES: dict[str, tuple[Path | None, str, str]] = {
    "basecoat-css": (None, "basecoat-factory.min.css", "style"),
    "basecoat-js-all": (None, "basecoat-js.min.js", "script"),
    "tailwind-browser": (None, TAILWIND_BROWSER_FILENAME, "script"),
}
LANDING_VERSION = "1.0.0"
LANDING_FILES: dict[str, tuple[Path, str, str]] = {
    "landing-css": (ASSETS_DST / "landing.css", "landing.css", "style"),
    "landing-js": (ASSETS_DST / "landing.js", "landing.js", "script"),
}
REMOTE_FILES: dict[str, tuple[None, str, str]] = {
    "htmx": (None, HTMX_FILENAME, "script"),
    "alpine": (None, ALPINE_FILENAME, "script"),
}
BUNDLED_FILES: dict[str, tuple[Path | None, str, str]] = {
    **CORE_FILES,
    **REMOTE_FILES,
    **LANDING_FILES,
}

LICENSE_SOURCES = {
    "htmx.LICENSE": (
        "HTMX",
        "0BSD",
        "https://github.com/bigskysoftware/htmx",
        HTMX_LICENSE_URL,
    ),
    "alpine.LICENSE": (
        "Alpine.js",
        "MIT",
        "https://github.com/alpinejs/alpine",
        ALPINE_LICENSE_URL,
    ),
    "tailwindcss.LICENSE": (
        "tailwindcss (@tailwindcss/browser runtime engine)",
        "MIT",
        "https://github.com/tailwindlabs/tailwindcss",
        TAILWIND_LICENSE_URL,
    ),
}


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


def fetch_npm_tarball(
    registry_url: str, *, package: str
) -> tuple[bytes, dict[str, object]]:
    metadata = json.loads(fetch_bytes(registry_url))
    dist = metadata.get("dist") if isinstance(metadata, dict) else None
    tarball = dist.get("tarball") if isinstance(dist, dict) else None
    integrity = dist.get("integrity") if isinstance(dist, dict) else None
    if not isinstance(tarball, str) or not tarball.startswith(
        "https://registry.npmjs.org/"
    ):
        raise RuntimeError(f"{package} registry metadata has no npm tarball")
    if not isinstance(integrity, str) or not integrity.startswith("sha512-"):
        raise RuntimeError(f"{package} registry metadata has no sha512 integrity")
    archive = fetch_bytes(tarball)
    digest = "sha512-" + base64.b64encode(hashlib.sha512(archive).digest()).decode(
        "ascii"
    )
    if not hmac.compare_digest(digest, integrity):
        raise RuntimeError(f"{package} tarball integrity mismatch")
    return archive, metadata


def extract_tarball_file(archive: bytes, member_path: str, *, package: str) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        member = tar.getmember(member_path)
        extracted = tar.extractfile(member)
        if extracted is None:
            raise RuntimeError(f"{package} tarball missing {member_path}")
        body = extracted.read()
    if not body:
        raise RuntimeError(f"{package} {member_path} is empty")
    return body


def fetch_alpine_cdn() -> bytes:
    archive, _metadata = fetch_npm_tarball(ALPINE_REGISTRY_URL, package="alpinejs")
    return extract_tarball_file(archive, ALPINE_DIST_PATH, package="alpinejs")


def fetch_tailwind_browser() -> bytes:
    archive, _metadata = fetch_npm_tarball(
        TAILWIND_BROWSER_REGISTRY_URL, package="@tailwindcss/browser"
    )
    return extract_tarball_file(
        archive, TAILWIND_BROWSER_DIST_PATH, package="@tailwindcss/browser"
    )


def fetch_basecoat() -> tuple[bytes, bytes, dict[str, object]]:
    archive, metadata = fetch_npm_tarball(BASECOAT_REGISTRY_URL, package="basecoat-css")
    css = extract_tarball_file(archive, BASECOAT_CDN_CSS_PATH, package="basecoat-css")
    js = extract_tarball_file(archive, BASECOAT_JS_PATH, package="basecoat-css")
    package_json = json.loads(
        extract_tarball_file(archive, "package/package.json", package="basecoat-css")
    )
    version = package_json.get("version")
    if version != BASECOAT_VERSION:
        raise RuntimeError(
            f"unreviewed basecoat-css version {version!r}; expected {BASECOAT_VERSION}"
        )
    if package_json.get("license") != "MIT":
        raise RuntimeError("basecoat-css package is not declared MIT")
    return css, js, {**package_json, "registry": metadata}


def compose_factory_css(basecoat_cdn_css: bytes) -> bytes:
    shell = (BUILD_SRC / "src" / "app-shell.css").read_bytes()
    theme = (BUILD_SRC / "src" / "app-theme.css").read_bytes()
    parts = (
        b"/* Basecoat CDN CSS (compiled components + tokens) */\n",
        basecoat_cdn_css.rstrip() + b"\n\n",
        b"/* Factory layout primitives */\n",
        shell.rstrip() + b"\n\n",
        b"/* Factory warm-paper light palette */\n",
        theme.rstrip() + b"\n",
    )
    return b"".join(parts)


def build_and_stage() -> Path:
    """Fetch pinned dist files and return a staging dir with the shipped layout."""
    if (BUILD_SRC / "package.json").exists() or (
        BUILD_SRC / "package-lock.json"
    ).exists():
        raise SystemExit("maintainer CSS build must not keep an npm lock")

    basecoat_css, basecoat_js, package_json = fetch_basecoat()
    factory_css = compose_factory_css(basecoat_css)
    alpine_js = fetch_alpine_cdn()
    tailwind_js = fetch_tailwind_browser()
    htmx_js = fetch_bytes(HTMX_SOURCE_URL)

    stage = Path(tempfile.mkdtemp(prefix="app-factory-assets-"))
    assets_stage = stage / "assets"
    assets_stage.mkdir()

    generated = {
        "basecoat-css": factory_css,
        "basecoat-js-all": basecoat_js,
        "tailwind-browser": tailwind_js,
        "htmx": htmx_js,
        "alpine": alpine_js,
    }
    for name, (_source, filename, _kind) in BUNDLED_FILES.items():
        if name in generated:
            (assets_stage / filename).write_bytes(generated[name])
            continue
        source = LANDING_FILES[name][0]
        if not source.is_file():
            raise RuntimeError(f"expected asset not found: {source}")
        shutil.copy2(source, assets_stage / filename)

    licenses_dir = assets_stage / "licenses"
    licenses_dir.mkdir()

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

    git_head = (
        package_json.get("registry", {}).get("gitHead")
        if isinstance(package_json.get("registry"), dict)
        else package_json.get("gitHead")
    )
    if not isinstance(git_head, str) or len(git_head) != 40:
        registry_metadata = json.loads(fetch_bytes(BASECOAT_REGISTRY_URL))
        git_head = registry_metadata.get("gitHead")
    if not isinstance(git_head, str) or len(git_head) != 40:
        raise RuntimeError(
            "basecoat-css registry metadata has no authoritative gitHead"
        )
    license_source = BASECOAT_LICENSE_URL.format(git_head=git_head)
    basecoat_license = fetch_bytes(license_source)
    validate_license(basecoat_license, license_source, required=BASECOAT_REQUIRED_TEXT)
    (licenses_dir / BASECOAT_LICENSE_FILENAME).write_bytes(basecoat_license)

    def asset_version(name: str) -> str:
        if name in LANDING_FILES:
            return LANDING_VERSION
        if name == "htmx":
            return HTMX_VERSION
        if name == "alpine":
            return ALPINE_VERSION
        if name == "tailwind-browser":
            return TAILWIND_BROWSER_VERSION
        return BASECOAT_VERSION

    manifest = {
        name: {
            "filename": filename,
            "version": asset_version(name),
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
    repository_directory = (
        repository.get("directory") if isinstance(repository, dict) else None
    )
    source = repository_url
    if isinstance(repository_directory, str) and repository_directory:
        source += f" ({repository_directory})"

    attribution = [
        "app-factory bundled platform assets",
        "",
        "Runtime/build provenance:",
    ]
    attribution.append(
        f"- basecoat-css {BASECOAT_VERSION}\n"
        f"  License: MIT\n"
        f"  Source: {source}\n"
        f"  Exact source commit: {git_head}\n"
        f"  Exact license: {license_source}\n"
        f"  License text: licenses/{BASECOAT_LICENSE_FILENAME}"
    )
    extra_sources = {
        "htmx.LICENSE": f"\n  Exact source: {HTMX_SOURCE_URL}",
        "alpine.LICENSE": (
            f"\n  Exact source: {ALPINE_REGISTRY_URL} ({ALPINE_DIST_PATH})"
        ),
        "tailwindcss.LICENSE": (
            f"\n  Exact source: {TAILWIND_BROWSER_REGISTRY_URL}"
            f" ({TAILWIND_BROWSER_DIST_PATH})"
        ),
    }
    version_labels = {
        "htmx.LICENSE": HTMX_VERSION,
        "alpine.LICENSE": ALPINE_VERSION,
        "tailwindcss.LICENSE": TAILWIND_BROWSER_VERSION,
    }
    for filename, (
        package,
        license_name,
        repository,
        source,
    ) in LICENSE_SOURCES.items():
        attribution.append(
            f"- {package} {version_labels[filename]}\n"
            f"  License: {license_name}\n"
            f"  Source: {repository}{extra_sources[filename]}\n"
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
        missing = [name for name in required if not (stage_assets / name).is_file()]
        if missing:
            raise RuntimeError(f"staging failed; missing: {missing}")
        replace_assets(stage_assets, ASSETS_DST)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    print("Done. Review and commit app_factory/assets.")


if __name__ == "__main__":
    main()
