"""The chrome-only starter stays executable and intentionally small."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).parents[1]
STARTER = ROOT / "examples" / "minimal_host"


def _load_starter():
    spec = importlib.util.spec_from_file_location(
        "minimal_host_app", STARTER / "app.py"
    )
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
    assert TestClient(module.app).get("/health").json() == {"status": "ok"}


def test_minimal_host_bootstrap_budget() -> None:
    """One composition call; no manual FastAPI/Jinja/static/context plumbing."""
    source = (STARTER / "app.py").read_text()
    tree = ast.parse(source)
    calls = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert calls.count("create_product_app") == 1
    assert not set(calls) & {
        "FastAPI",
        "Jinja2Templates",
        "install_platform",
        "install_platform_request_context",
        "install_identity_adapters",
    }
    # Imports, menu/config and composition included; domain endpoint excluded.
    bootstrap_lines = [
        line
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert len(bootstrap_lines) <= 30
