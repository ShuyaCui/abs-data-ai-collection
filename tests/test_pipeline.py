from __future__ import annotations

import json
from pathlib import Path

from npl_extract.parsers import Block, PageContent, PageRoute, PypdfNativeParser, route_page
from npl_extract.pipeline import persist_page_artifacts


def test_routes_native_scan_and_complex_table_pages() -> None:
    assert route_page(PageContent(1, "证券代码 ABC123", [])) is PageRoute.NATIVE
    assert route_page(PageContent(2, "", [])) is PageRoute.OCR
    assert route_page(PageContent(2, "A", [])) is PageRoute.OCR
    assert route_page(PageContent(3, "表格文字", [], has_complex_table=True)) is PageRoute.HYBRID


def test_persists_idempotent_evidence_artifacts(tmp_path: Path) -> None:
    pages = [
        PageContent(
            1,
            "证券代码 ABC123",
            [Block("p001:b001", 1, "证券代码 ABC123", [0, 0, 72, 12])],
        ),
        PageContent(2, "", []),
    ]

    first = persist_page_artifacts("a" * 64, pages, tmp_path)
    second = persist_page_artifacts("a" * 64, pages, tmp_path)

    assert not first.reused
    assert second.reused
    assert (first.run_dir / "manifest.json").is_file()
    assert (first.run_dir / "page-quality.jsonl").is_file()
    assert (first.run_dir / "blocks.jsonl").is_file()
    assert (first.run_dir / "tables.jsonl").is_file()
    diagnostics = [json.loads(line) for line in (first.run_dir / "page-quality.jsonl").read_text().splitlines()]
    assert [entry["route"] for entry in diagnostics] == ["native", "ocr"]


def test_repairs_an_incomplete_artifact_run_instead_of_reusing_it(tmp_path: Path) -> None:
    pages = [PageContent(1, "证券代码 ABC123", [Block("p001:b001", 1, "证券代码 ABC123", [0, 0, 72, 12])])]
    first = persist_page_artifacts("b" * 64, pages, tmp_path)
    (first.run_dir / "blocks.jsonl").unlink()

    repaired = persist_page_artifacts("b" * 64, pages, tmp_path)

    assert not repaired.reused
    assert (repaired.run_dir / "blocks.jsonl").is_file()


def test_repairs_a_run_created_by_a_different_pipeline_version(tmp_path: Path) -> None:
    pages = [PageContent(1, "证券代码 ABC123", [])]
    first = persist_page_artifacts("c" * 64, pages, tmp_path)
    manifest_path = first.run_dir / "manifest.json"
    manifest_path.write_text('{"document_sha256":"' + "c" * 64 + '","pipeline_version":"old"}')

    repaired = persist_page_artifacts("c" * 64, pages, tmp_path)

    assert not repaired.reused


def test_native_parser_preserves_page_text_and_evidence_id(tmp_path: Path) -> None:
    source = tmp_path / "native.pdf"
    source.write_bytes(_text_pdf("Security ABC123"))

    pages = PypdfNativeParser().parse(source)

    assert pages[0].physical_page == 1
    assert "ABC123" in pages[0].native_text
    assert pages[0].blocks[0].evidence_id == "p001:b001"
    assert pages[0].blocks[0].bbox is None


def _text_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 10 50 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> /MediaBox [0 0 72 72] /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, item in enumerate(objects, start=1):
        offsets.append(len(body))
        body.extend(f"{number} 0 obj\n".encode())
        body.extend(item)
        body.extend(b"\nendobj\n")
    xref = len(body)
    body.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    body.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    body.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(body)
