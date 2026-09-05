from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from jinja2 import Environment
from starlette.datastructures import Headers, UploadFile

from app_factory import (
    UploadLimitExceeded,
    read_upload_bounded,
    read_uploads_bounded,
)
from app_factory.jinja import configure_jinja_env


def _render(**kwargs: object) -> str:
    env = configure_jinja_env(Environment(autoescape=True))
    template = env.from_string(
        '{% from "app_factory/components/file_upload.html" import file_upload %}'
        '{{ file_upload(**options) }}'
    )
    return template.render(options=kwargs)


def test_upload_is_domain_blind_and_host_configurable() -> None:
    html = _render(
        id="evidence",
        action="/evidence",
        name="documents",
        accept=".custom,application/x-custom",
        multiple=True,
        max_bytes=1234,
        choose_label="Choose evidence",
        drop_label="Drop evidence",
        submit_label="Send evidence",
        target="#result",
    )
    assert 'action="/evidence"' in html
    assert 'hx-post="/evidence"' in html
    assert 'hx-encoding="multipart/form-data"' in html
    assert 'hx-target="#result"' in html
    assert 'name="documents"' in html
    assert 'accept=".custom,application/x-custom"' in html
    assert "multiple" in html
    assert 'data-max-bytes="1234"' in html
    assert "DOCX" not in html and "PDF" not in html


def test_upload_has_accessible_progress_and_no_js_fallback() -> None:
    html = _render(id="upload", action="/upload")
    assert 'method="post"' in html
    assert 'enctype="multipart/form-data"' in html
    assert 'type="file"' in html
    assert 'tabindex="0"' in html
    assert 'aria-live="polite"' in html
    assert 'hx-encoding="multipart/form-data"' in html
    assert "<progress" in html
    assert 'type="submit"' in html


def test_client_shell_interactivity_is_opt_in() -> None:
    env = configure_jinja_env(Environment(autoescape=True))
    context = {
        "platform_paths": {"login": "/login", "register": "/register"},
        "platform_user": None,
        "platform_show_register": False,
        "platform_locales": (),
    }
    slim = env.get_template("app_factory/client_shell.html").render(**context)
    interactive = env.get_template("app_factory/client_shell.html").render(
        **context, client_interactive=True
    )
    assert "/static/platform/htmx.min.js" not in slim
    assert "/static/platform/alpine.min.js" not in slim
    assert "/static/platform/htmx.min.js" in interactive
    assert "/static/platform/alpine.min.js" in interactive
    assert "__appFileUploadBooted" in interactive


def test_shared_controller_uses_htmx_transport_not_fetch_or_xhr() -> None:
    source = (
        configure_jinja_env(Environment(autoescape=True))
        .get_template("app_factory/file_upload_boot.html")
        .render()
    )
    assert "new XMLHttpRequest" not in source
    assert "fetch(" not in source
    assert "htmx:xhr:progress" in source
    assert "DataTransfer" in source
    assert "requestSubmit" in source


def test_single_file_upload_does_not_render_batch_confirmation_field() -> None:
    html = _render(id="upload", action="/upload", multiple=False)
    assert "data-app-file-confirmed-count" not in html
    assert 'data-label-confirm=""' in html


def test_upload_field_help_is_automatically_described() -> None:
    env = configure_jinja_env(Environment(autoescape=True))
    html = env.from_string(
        '{% from "app_factory/components/file_upload.html" import file_upload_field %}'
        '{{ file_upload_field(id="docs", help_text="Maximum 5 MB") }}'
    ).render()
    assert 'id="docs-help"' in html
    assert 'aria-describedby="docs-help"' in html


def test_read_upload_bounded_returns_metadata_and_bytes() -> None:
    upload = UploadFile(
        BytesIO(b"document"),
        filename="evidence.bin",
        headers=Headers({"content-type": "application/x-evidence"}),
    )
    result = asyncio.run(read_upload_bounded(upload, max_bytes=8, chunk_size=3))
    assert result.filename == "evidence.bin"
    assert result.content_type == "application/x-evidence"
    assert result.data == b"document"


def test_read_upload_bounded_stops_after_limit() -> None:
    upload = UploadFile(BytesIO(b"too large"), filename="large.bin")
    with pytest.raises(UploadLimitExceeded) as raised:
        asyncio.run(read_upload_bounded(upload, max_bytes=4, chunk_size=3))
    assert raised.value.max_bytes == 4
    assert raised.value.filename == "large.bin"
    assert upload.file.tell() <= 6


def test_read_upload_bounded_accepts_exact_limit_and_empty_file() -> None:
    exact = UploadFile(BytesIO(b"1234"), filename="exact.bin")
    assert asyncio.run(read_upload_bounded(exact, max_bytes=4, chunk_size=2)).data == b"1234"
    empty = UploadFile(BytesIO(b""), filename=None)
    result = asyncio.run(read_upload_bounded(empty, max_bytes=1))
    assert result.filename == "upload"
    assert result.content_type == "application/octet-stream"
    assert result.data == b""


def test_read_upload_bounded_validates_limits() -> None:
    upload = UploadFile(BytesIO(b"x"), filename="x")
    with pytest.raises(ValueError, match="max_bytes"):
        asyncio.run(read_upload_bounded(upload, max_bytes=0))
    with pytest.raises(ValueError, match="chunk_size"):
        asyncio.run(read_upload_bounded(upload, max_bytes=1, chunk_size=0))


def test_read_uploads_bounded_enforces_file_count_and_total_size() -> None:
    uploads = [
        UploadFile(BytesIO(b"one"), filename="one.bin"),
        UploadFile(BytesIO(b"two"), filename="two.bin"),
    ]
    result = asyncio.run(
        read_uploads_bounded(uploads, max_file_bytes=3, max_total_bytes=6, max_files=2)
    )
    assert [item.filename for item in result] == ["one.bin", "two.bin"]

    too_many = [UploadFile(BytesIO(b"x"), filename=str(index)) for index in range(3)]
    with pytest.raises(UploadLimitExceeded, match="file count"):
        asyncio.run(
            read_uploads_bounded(
                too_many, max_file_bytes=2, max_total_bytes=4, max_files=2
            )
        )

    too_large = [
        UploadFile(BytesIO(b"123"), filename="one.bin"),
        UploadFile(BytesIO(b"456"), filename="two.bin"),
    ]
    with pytest.raises(UploadLimitExceeded, match="total"):
        asyncio.run(
            read_uploads_bounded(
                too_large, max_file_bytes=3, max_total_bytes=5, max_files=2
            )
        )


def test_upload_field_composes_inside_a_host_form() -> None:
    env = configure_jinja_env(Environment(autoescape=True))
    template = env.from_string(
        '{% from "app_factory/components/file_upload.html" import file_upload_field %}'
        '<form method="post" data-app-file-upload>'
        '{{ file_upload_field(id="pdf", name="evidence", accept=".pdf") }}'
        '<button data-app-file-submit>Save project</button></form>'
    )
    html = template.render()
    assert html.count("<form") == 1
    assert 'data-app-file-upload-field' in html
    assert 'name="evidence"' in html
    assert 'accept=".pdf"' in html
    html = env.from_string(
        '{% from "app_factory/components/file_upload.html" import file_upload_field %}'
        '{{ file_upload_field(id="docs", name="files", describedby="hint other") }}'
    ).render()
    assert 'aria-describedby="hint other"' in html
