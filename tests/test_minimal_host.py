"""The chrome-only starter stays executable and intentionally small."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).parents[1]
STARTER = ROOT / "examples" / "minimal_host"


def _load_starter():
    spec = importlib.util.spec_from_file_location("minimal_host_app", STARTER / "app.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_minimal_host_renders_shared_product_shell() -> None:
    module = _load_starter()

    response = TestClient(module.app).get("/")

    assert response.status_code == 200
    assert "Small AI tool" in response.text
    assert "/static/platform/basecoat-factory.min.css" in response.text
    assert 'aria-current="page"' in response.text
    assert not (STARTER / "static").exists()
