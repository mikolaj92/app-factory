"""Chrome lives in files. Python is one binding, not a second copy."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "app_factory"
TEMPLATES = PACKAGE / "templates" / "app_factory"
CONTRACT = PACKAGE / "contract"
PYTHON_SOURCES = (
    PACKAGE / "csrf.py",
    PACKAGE / "product_errors.py",
    PACKAGE / "responses.py",
    PACKAGE / "platform.py",
)


def test_python_chrome_modules_do_not_embed_html_markup() -> None:
    markup = re.compile(r"<(div|section|p|span|html|body|alert)\b", re.I)
    for path in PYTHON_SOURCES:
        text = path.read_text(encoding="utf-8")
        match = markup.search(text)
        assert match is None, f"{path.relative_to(REPO)} embeds HTML: {match.group(0)!r}"


def test_platform_paths_defaults_come_from_contract_file() -> None:
    import tomllib

    from app_factory.platform import (
        IDENTITY_ADMIN_SURFACES,
        IDENTITY_AUTHENTICATED_SURFACES,
        IDENTITY_PUBLIC_SURFACES,
        PlatformPaths,
    )

    contract = tomllib.loads(
        (CONTRACT / "paths.toml").read_text(encoding="utf-8")
    )["paths"]
    paths = PlatformPaths()
    for name, value in contract.items():
        assert getattr(paths, name) == value, name
    assert set(paths.public_hrefs()) == set(IDENTITY_PUBLIC_SURFACES)
    assert set(paths.authenticated_hrefs()) == set(IDENTITY_AUTHENTICATED_SURFACES)
    assert set(paths.admin_hrefs()) == set(IDENTITY_ADMIN_SURFACES)


def test_http_contract_file_is_the_redirect_and_csrf_source() -> None:
    import tomllib

    from app_factory.contract import http_contract
    from app_factory.responses import same_origin_return_path

    raw = tomllib.loads((CONTRACT / "http.toml").read_text(encoding="utf-8"))
    contract = http_contract()
    assert contract == raw
    next_rule = contract["login_redirect"]["next"]
    for value in next_rule["accept"]:
        assert same_origin_return_path(value) == value
    for value in next_rule["reject"]:
        assert same_origin_return_path(value) is None
    csrf = contract["origin_csrf"]
    assert csrf["json_error"] == "CSRF validation failed"
    assert csrf["json_detail"] == "Invalid or missing Origin."
    assert csrf["htmx_template"] == "app_factory/csrf_origin_denied.html"
    assert csrf["htmx_status"] == 403
    assert csrf["json_status"] == 403
    htmx = contract["htmx_redirect"]
    assert htmx["status"] == 303
    assert htmx["header"] == "HX-Redirect"
    assert htmx["request_header"] == "HX-Request"


def test_jinja_templates_stay_inside_declared_subset() -> None:
    import tomllib

    from app_factory.contract import http_contract

    subset = http_contract()["jinja"]
    raw = tomllib.loads((CONTRACT / "http.toml").read_text(encoding="utf-8"))["jinja"]
    assert subset == raw
    tag_re = re.compile(r"\{%-?\s*([a-z]+)")
    stmt_re = re.compile(r"\{%.*?%\}", re.S)
    expr_re = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
    filt_re = re.compile(r"\|\s*([a-zA-Z_][a-zA-Z0-9_]*)")
    test_re = re.compile(r"\bis\s+(?:not\s+)?([a-zA-Z_][a-zA-Z0-9_]*)")
    quoted = re.compile(r"['\"][^'\"]*['\"]")
    used_tags: set[str] = set()
    used_filters: set[str] = set()
    used_tests: set[str] = set()
    for path in TEMPLATES.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        used_tags.update(tag_re.findall(text))
        for expr in expr_re.findall(text):
            used_filters.update(filt_re.findall(quoted.sub("", expr)))
        for stmt in stmt_re.findall(text):
            used_tests.update(test_re.findall(quoted.sub("", stmt)))
    allowed_tags = set(subset["tags"])
    allowed_filters = set(subset["filters"])
    allowed_tests = set(subset["tests"])
    assert used_tags <= allowed_tags, sorted(used_tags - allowed_tags)
    assert used_filters <= allowed_filters, sorted(used_filters - allowed_filters)
    assert used_tests <= allowed_tests, sorted(used_tests - allowed_tests)
