from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError


DEFAULT_MAX_BYTES = 200 * 1024 * 1024
DEFAULT_MAX_PAGES = 5_000


class FailureCode(str, Enum):
    NOT_PDF = "NOT_PDF"
    BYTE_LIMIT_EXCEEDED = "BYTE_LIMIT_EXCEEDED"
    PAGE_LIMIT_EXCEEDED = "PAGE_LIMIT_EXCEEDED"
    ENCRYPTED_PDF = "ENCRYPTED_PDF"
    MALFORMED_PDF = "MALFORMED_PDF"
    ACTIVE_CONTENT = "ACTIVE_CONTENT"
    EMBEDDED_FILE = "EMBEDDED_FILE"


@dataclass(frozen=True)
class IntakeResult:
    accepted: bool
    document_sha256: str | None
    page_count: int | None
    failure_code: FailureCode | None


def _dictionary(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def _has_active_content(reader: PdfReader) -> FailureCode | None:
    root = _dictionary(reader.trailer["/Root"])
    if "/OpenAction" in root or "/AA" in root:
        return FailureCode.ACTIVE_CONTENT
    names = _dictionary(root.get("/Names", {}))
    if "/EmbeddedFiles" in names:
        return FailureCode.EMBEDDED_FILE
    if "/JavaScript" in names:
        return FailureCode.ACTIVE_CONTENT
    for page in reader.pages:
        page_data = _dictionary(page)
        if "/AA" in page_data:
            return FailureCode.ACTIVE_CONTENT
    return None


def inspect_pdf(
    path: Path,
    *,
    input_root: Path | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> IntakeResult:
    """Inspect a PDF without writing it or invoking an untrusted parser process."""
    source = path.resolve(strict=True)
    if input_root is not None:
        try:
            source.relative_to(input_root.resolve(strict=True))
        except ValueError as error:
            raise ValueError("PDF path must be inside the configured input root") from error

    if source.stat().st_size > max_bytes:
        return IntakeResult(False, None, None, FailureCode.BYTE_LIMIT_EXCEEDED)
    content = source.read_bytes()
    if not content.startswith(b"%PDF-"):
        return IntakeResult(False, None, None, FailureCode.NOT_PDF)
    digest = sha256(content).hexdigest()
    try:
        reader = PdfReader(source)
        if reader.is_encrypted:
            return IntakeResult(False, digest, None, FailureCode.ENCRYPTED_PDF)
        page_count = len(reader.pages)
        if page_count > max_pages:
            return IntakeResult(False, digest, page_count, FailureCode.PAGE_LIMIT_EXCEEDED)
        failure = _has_active_content(reader)
    except (PdfReadError, KeyError, OSError, ValueError):
        return IntakeResult(False, digest, None, FailureCode.MALFORMED_PDF)
    if failure:
        return IntakeResult(False, digest, page_count, failure)
    return IntakeResult(True, digest, page_count, None)
