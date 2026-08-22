"""Session-backed CSRF adapter for FastAPI/Starlette hosts."""

from __future__ import annotations

import secrets
from typing import cast

try:
    from fastapi import Request
except ImportError as exc:
    raise ImportError("app_factory.csrf requires app-factory[fastapi]") from exc


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
