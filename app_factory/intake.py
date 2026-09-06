"""Small declarative intake contract; no persistence or workflow state."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app_factory.uploads import UploadedFile


def _name(value: str) -> None:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", value) or value in {
        "csrf_token",
        "idempotency_key",
    }:
        raise ValueError("Use a non-reserved identifier for intake names/ids")


@dataclass(frozen=True, slots=True)
class IntakeField:
    name: str
    label: str
    kind: Literal["text", "select"] = "text"
    required: bool = False
    max_length: int = 4096
    options: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        _name(self.name)
        if self.kind not in {"text", "select"} or self.max_length <= 0:
            raise ValueError("Invalid field kind or length")
        if len(dict(self.options)) != len(self.options):
            raise ValueError("Option values must be unique")


@dataclass(frozen=True, slots=True)
class IntakeFiles:
    name: str = "files"
    label: str = "Choose files"
    accept: str = ""
    required: bool = False
    max_files: int = 10
    max_file_bytes: int = 5 * 1024 * 1024
    max_total_bytes: int = 15 * 1024 * 1024

    def __post_init__(self):
        _name(self.name)
        if min(self.max_files, self.max_file_bytes, self.max_total_bytes) <= 0:
            raise ValueError("Upload limits must be positive")


@dataclass(frozen=True, slots=True)
class IntakeSpec:
    fields: tuple[IntakeField, ...] = ()
    id: str = "intake"
    title: str = "Start"
    submit_label: str = "Start"
    files: IntakeFiles | None = None
    max_request_bytes: int = 16 * 1024 * 1024

    def __post_init__(self):
        _name(self.id)
        names = [field.name for field in self.fields]
        if self.files:
            names.append(self.files.name)
        if len(set(names)) != len(names) or self.max_request_bytes <= 0:
            raise ValueError("Names must be unique and request limit positive")


class IntakeError(Exception):
    """Public field errors; the empty key denotes a form-level error.

    Messages must be safe to expose. Unknown field names render at form level.
    """

    def __init__(self, errors: Mapping[str, str], *, status_code: int = 422):
        self.errors = dict(errors)
        self.status_code = status_code
        super().__init__("Invalid intake")


@dataclass(frozen=True, slots=True)
class IntakeSubmission:
    """Validated mechanics. Host may persist bytes and put stable refs in intent.

    Scope plus idempotency_key lets host storage deduplicate upload side effects.
    No file storage or cleanup policy is provided by app-factory.
    """

    fields: dict[str, str]
    idempotency_key: str
    files: tuple["UploadedFile", ...] = ()
