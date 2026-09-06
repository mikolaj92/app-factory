"""Version 1 presentation contract; hosts own execution, storage and policy.

Requires app-factory[fastapi] (Pydantic v2). No workflow engine is imported.
"""

from collections.abc import AsyncIterable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

# queued remains accepted for existing v1 hosts; HTML presents it as pending.
RunStatus = Literal[
    "queued", "pending", "running", "waiting", "succeeded", "failed", "cancelled"
]
RetryAfter = Annotated[int, Field(ge=1)]
RunAction = Literal["create", "read", "cancel", "artifact"]
NonEmpty = Annotated[str, Field(min_length=1)]
ArtifactBody = Iterable[bytes] | AsyncIterable[bytes]


class _RunDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal["v1"] = "v1"


class RunIntent(_RunDTO):
    """Opaque product input; only the host interprets or validates its meaning."""

    kind: NonEmpty
    input: dict[str, JsonValue] = Field(default_factory=dict)


class Run(_RunDTO):
    id: NonEmpty
    status: RunStatus
    created_at: datetime
    waiting_reason: str | None = None
    next_observation: str | None = None
    retry_after: RetryAfter | None = None


class RunPage(_RunDTO):
    items: list[Run]
    next_cursor: NonEmpty | None = None


class RunArtifact(_RunDTO):
    """Typed result reference. Bytes stay behind a host-owned artifact port."""

    id: NonEmpty
    media_type: NonEmpty
    label: NonEmpty | None = None
    size: Annotated[int, Field(ge=0)] | None = None
    digest: NonEmpty | None = None
    disposition: Literal["inline", "attachment"] | None = None
    filename: NonEmpty | None = None
    href: NonEmpty | None = None
    name: NonEmpty | None = None

    @model_validator(mode="after")
    def _compat_label(self) -> "RunArtifact":
        label = self.label or self.name
        if not label:
            raise ValueError("label or name is required")
        if self.label is None:
            object.__setattr__(self, "label", label)
        if self.name is None:
            object.__setattr__(self, "name", label)
        return self


class RunArtifacts(_RunDTO):
    items: list[RunArtifact]


class RunResult(_RunDTO):
    """Domain-neutral terminal values, external links, and downloadable artifacts."""

    run_id: NonEmpty
    values: dict[str, JsonValue] = Field(default_factory=dict)
    links: list[RunArtifact] = Field(default_factory=list)
    artifacts: list[RunArtifact] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RunArtifactStream:
    """Host-owned byte stream plus the metadata the router must re-validate."""

    artifact: RunArtifact
    body: ArtifactBody
    digest: str | None = None


RunErrorCode = Literal[
    "unauthorized",
    "forbidden",
    "not_found",
    "conflict",
    "invalid_request",
    "unavailable",
    "stale_version",
]


class RunErrorResponse(_RunDTO):
    code: RunErrorCode
    message: str
    retry_after: RetryAfter | None = None


class RunError(Exception):
    """Expected public failure. Message MUST be safe to expose to clients."""

    def __init__(
        self, code: RunErrorCode, message: str, *, retry_after: int | None = None
    ) -> None:
        self.response = RunErrorResponse(
            code=code, message=message, retry_after=retry_after
        )
        super().__init__(message)


class RunPort(Protocol):
    """Async host adapter. Scope is an opaque authorization partition.

    ``create_intent`` MUST atomically deduplicate (scope, idempotency_key),
    including concurrent retries and across workers/restarts. Reusing a key
    with different intent MUST raise RunError('conflict', ...). The host owns
    retention of that mapping; the router never caches or persists run state.
    Every operation MUST restrict access to scope, including history items.
    """

    async def create_intent(
        self, scope: str, intent: RunIntent, *, idempotency_key: str
    ) -> Run: ...

    async def get_run(self, scope: str, run_id: str) -> Run:
        """Return current presentation state or raise not_found."""
        ...

    async def list_runs(self, scope: str, *, cursor: str | None, limit: int) -> RunPage:
        """Stable host ordering; opaque scope-bound cursor, at most limit items.

        Reject invalid/foreign cursors with invalid_request. None ends history.
        """
        ...

    async def request_cancel(self, scope: str, run_id: str) -> Run:
        """Request cancellation, not forced termination; return current state.

        Repeats must be safe. The host may still report running while pending.
        """
        ...

    async def list_artifacts(self, scope: str, run_id: str) -> RunArtifacts:
        """List available result links; empty is valid before completion.

        Links must be independently authorized or short-lived scoped URLs.
        """
        ...

    async def get_result(self, scope: str, run_id: str) -> RunResult:
        """Return terminal values/links/artifacts without interpreting domain bytes."""
        ...

    async def open_artifact(
        self, scope: str, run_id: str, artifact_id: str
    ) -> RunArtifactStream:
        """Open a scoped stream. Pending/expired/missing/mismatch MUST raise RunError."""
        ...
