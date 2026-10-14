"""Exercise the supported TestClient transport, not only dependency metadata."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


def test_testclient_uses_httpx2_and_preserves_error_responses(tmp_path, capsys) -> None:
    assert importlib.util.find_spec("httpx2") is not None
    import httpx2

    app = FastAPI()

    @app.get("/denied")
    def denied():
        raise HTTPException(status_code=403, detail="denied")

    with TestClient(app) as client:
        assert isinstance(client, httpx2.Client)
        response = client.get("/denied")
    assert response.status_code == 403
    assert response.json() == {"detail": "denied"}

    spec = importlib.util.spec_from_file_location(
        "refresh_platform_assets",
        Path(__file__).resolve().parents[1] / "scripts/refresh_platform_assets.py",
    )
    refresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(refresh)
    packages = ("fastapi", "starlette", "uvicorn", "httpx2")
    for relative in ("uv.lock", "examples/multi_user_bom/uv.lock"):
        lock = tmp_path / relative
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("\n".join(
            f'[[package]]\nname = "{name}"\nversion = "1.0"'
            for name in packages
        ))
    metadata = {"releases": {
        "1.0": [{"yanked": False}],
        "2.0rc1": [{"yanked": False}],
        "2.0.dev1": [{"yanked": False}],
        "3.0": [{"yanked": True}],
        "4.0": [],
    }}
    with patch.object(refresh, "REPO_ROOT", tmp_path), patch.object(
        refresh, "fetch_bytes", return_value=json.dumps(metadata).encode(),
    ):
        assert refresh.check_http_releases() == 0
        report = json.loads(capsys.readouterr().out)
        assert report["outdated"] == 0
        assert len(report["packages"]) == 8
        metadata["releases"]["2.0"] = [{"yanked": False}]
        with patch.object(refresh, "fetch_bytes", return_value=json.dumps(metadata).encode()):
            assert refresh.check_http_releases() == 1
            assert json.loads(capsys.readouterr().out)["outdated"] == 8

        for invalid in (
            {}, {"releases": []}, {"releases": {}},
            {"releases": {"not-a-version": [{}]}},
            {"releases": {"1.0": [None]}},
            {"releases": {"1.0": [{"yanked": "false"}]}},
            {"releases": {"2.0rc1": [{}]}},
        ):
            with patch.object(refresh, "fetch_bytes", return_value=json.dumps(invalid).encode()):
                with pytest.raises(RuntimeError, match="fastapi.*release"):
                    refresh.check_http_releases()
        with patch.object(refresh, "fetch_bytes", return_value=b"not JSON"):
            with pytest.raises(RuntimeError, match="fastapi.*release"):
                refresh.check_http_releases()
        with patch.object(refresh, "fetch_bytes", side_effect=TimeoutError("timed out")):
            with pytest.raises(RuntimeError, match="fastapi.*timed out"):
                refresh.check_http_releases()
