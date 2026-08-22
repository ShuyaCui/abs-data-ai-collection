from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

from npl_extract.intake import FailureCode, inspect_pdf


def pdf_bytes(*, encrypted: bool = False, javascript: bool = False, attachment: bool = False) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt("secret")
    if javascript:
        writer.add_js("app.alert('no');")
    if attachment:
        writer.add_attachment("payload.txt", b"not allowed")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def write(tmp_path: Path, name: str, content: bytes) -> Path:
    target = tmp_path / name
    target.write_bytes(content)
    return target


def test_accepts_a_small_inert_pdf(tmp_path: Path) -> None:
    result = inspect_pdf(write(tmp_path, "safe.pdf", pdf_bytes()))

    assert result.accepted
    assert result.page_count == 1
    assert result.document_sha256


@pytest.mark.parametrize(
    ("name", "content", "expected"),
    [
        ("not-a-pdf.pdf", b"hello", FailureCode.NOT_PDF),
        ("encrypted.pdf", pdf_bytes(encrypted=True), FailureCode.ENCRYPTED_PDF),
        ("script.pdf", pdf_bytes(javascript=True), FailureCode.ACTIVE_CONTENT),
        ("attachment.pdf", pdf_bytes(attachment=True), FailureCode.EMBEDDED_FILE),
    ],
)
def test_quarantines_unsafe_or_invalid_pdf(
    tmp_path: Path, name: str, content: bytes, expected: FailureCode
) -> None:
    result = inspect_pdf(write(tmp_path, name, content))

    assert not result.accepted
    assert result.failure_code is expected


def test_quarantines_an_over_limit_pdf(tmp_path: Path) -> None:
    result = inspect_pdf(write(tmp_path, "large.pdf", pdf_bytes()), max_bytes=16)

    assert not result.accepted
    assert result.failure_code is FailureCode.BYTE_LIMIT_EXCEEDED


def test_refuses_a_path_outside_the_configured_input_root(tmp_path: Path) -> None:
    outside = write(tmp_path.parent, "outside.pdf", pdf_bytes())

    with pytest.raises(ValueError, match="input root"):
        inspect_pdf(outside, input_root=tmp_path)
