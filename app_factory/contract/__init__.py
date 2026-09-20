"""Language-neutral chrome files. Bindings read; they do not copy."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast


def _load(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        tomllib.loads(files(__package__).joinpath(name).read_text(encoding="utf-8")),
    )


@lru_cache(maxsize=1)
def identity_paths() -> dict[str, str]:
    return dict(_load("paths.toml")["paths"])


@lru_cache(maxsize=1)
def http_contract() -> dict[str, Any]:
    return _load("http.toml")
