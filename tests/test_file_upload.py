from __future__ import annotations

from jinja2 import Environment

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
    assert "htmx:xhr:progress" in html
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
