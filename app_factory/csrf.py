"""Session-backed CSRF adapter for FastAPI/Starlette hosts."""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from typing import cast
from urllib.parse import urlsplit

try:
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware
except ImportError as exc:
    raise ImportError("app_factory.csrf requires app-factory[fastapi]") from exc


_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def _origin_of(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


class SameOriginCsrfMiddleware(BaseHTTPMiddleware):
    """Reject cross-origin unsafe browser requests.

    The request host is always accepted. Hosts may add trusted origins and
    explicit path-prefix exemptions for webhooks or other cross-origin APIs.
    """

    def __init__(
        self,
        app: object,
        *,
        trusted_origins: Iterable[str] = (),
        exempt_prefixes: Iterable[str] = (),
        allow_missing_origin: bool = False,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.trusted_origins = frozenset(
            normalized
            for origin in trusted_origins
            if (normalized := (_origin_of(origin) or origin))
        )
        self.exempt_prefixes = tuple(exempt_prefixes)
        self.allow_missing_origin = allow_missing_origin

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method in _SAFE_METHODS or any(
            request.url.path.startswith(prefix) for prefix in self.exempt_prefixes
        ):
            return await call_next(request)

        candidate = request.headers.get("origin") or request.headers.get("referer")
        supplied = _origin_of(candidate)
        request_origin = _origin_of(str(request.base_url))
        if supplied is None and self.allow_missing_origin:
            return await call_next(request)
        if supplied is None or supplied not in self.trusted_origins | {request_origin}:
            if request.headers.get("HX-Request", "").lower() == "true":
                return HTMLResponse(
                    '<div class="alert" data-variant="destructive" role="alert">'
                    "Request blocked: invalid origin. Please reload the page and "
                    "try again.</div>",
                    status_code=403,
                )
            return JSONResponse(
                {"error": "CSRF validation failed", "detail": "Invalid or missing Origin."},
                status_code=403,
            )
        return await call_next(request)


class SessionCsrfProtection:
    """CSRF token stored in a signed Starlette session.

    The host remains responsible for installing ``SessionMiddleware``. This
    adapter implements my-usermanager's structural ``CsrfProtection`` protocol
    without importing that optional package.
    """

    def __init__(self, *, session_key: str = "app_factory_csrf") -> None:
        if not session_key:
            raise ValueError("session_key is required")
        self._session_key = session_key

    def token(self, request: Request) -> str:
        """Return the stable request-session token, minting it when absent."""
        session = self._session(request)
        existing = session.get(self._session_key)
        if isinstance(existing, str) and existing:
            return existing
        token = secrets.token_urlsafe(32)
        session[self._session_key] = token
        return token

    def validate(self, request: Request, submitted_token: str) -> None:
        """Raise ``PermissionError`` unless the submitted token matches."""
        session = self._session(request)
        expected = session.get(self._session_key)
        if (
            not isinstance(expected, str)
            or not expected
            or not isinstance(submitted_token, str)
            or not secrets.compare_digest(expected, submitted_token)
        ):
            raise PermissionError("invalid csrf token")

    @staticmethod
    def _session(request: Request) -> dict[str, object]:
        if "session" not in request.scope:
            raise RuntimeError("SessionMiddleware is required for session CSRF")
        return cast(dict[str, object], request.session)
