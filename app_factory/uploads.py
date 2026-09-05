"""Small bounded-upload primitive for FastAPI/Starlette hosts."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from starlette.datastructures import UploadFile
except ImportError as exc:
    raise ImportError("app_factory.uploads requires app-factory[fastapi]") from exc


@dataclass(frozen=True, slots=True)
class UploadedFile:
    """One upload read into memory after enforcing a byte limit."""

    filename: str
    content_type: str
    data: bytes


class UploadLimitExceeded(ValueError):
    """Raised as soon as an upload batch exceeds a configured limit."""

    def __init__(self, filename: str, max_bytes: int, *, reason: str = "file") -> None:
        super().__init__(f"upload {reason} exceeds {max_bytes}: {filename}")
        self.filename = filename
        self.max_bytes = max_bytes
        self.reason = reason


async def read_upload_bounded(
    upload: UploadFile,
    *,
    max_bytes: int,
    chunk_size: int = 64 * 1024,
) -> UploadedFile:
    """Read one ``UploadFile`` without accepting more than ``max_bytes``.

    File-format, malware, archive, and product policy validation stay in the
    consumer. The caller remains responsible for closing the ``UploadFile``.
    """
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(chunk_size):
        total += len(chunk)
        if total > max_bytes:
            raise UploadLimitExceeded(upload.filename or "upload", max_bytes)
        chunks.append(chunk)
    return UploadedFile(
        filename=upload.filename or "upload",
        content_type=upload.content_type or "application/octet-stream",
        data=b"".join(chunks),
    )


async def read_uploads_bounded(
    uploads: list[UploadFile],
    *,
    max_file_bytes: int,
    max_total_bytes: int,
    max_files: int,
    chunk_size: int = 64 * 1024,
) -> tuple[UploadedFile, ...]:
    """Read a bounded batch, enforcing count, per-file, and aggregate limits."""
    if max_files <= 0:
        raise ValueError("max_files must be positive")
    if max_total_bytes <= 0:
        raise ValueError("max_total_bytes must be positive")
    if len(uploads) > max_files:
        raise UploadLimitExceeded(
            "batch", max_files, reason="file count"
        )

    result: list[UploadedFile] = []
    total = 0
    for upload in uploads:
        item = await read_upload_bounded(
            upload, max_bytes=max_file_bytes, chunk_size=chunk_size
        )
        total += len(item.data)
        if total > max_total_bytes:
            raise UploadLimitExceeded(
                item.filename, max_total_bytes, reason="total size"
            )
        result.append(item)
    return tuple(result)
