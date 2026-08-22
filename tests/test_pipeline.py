from __future__ import annotations

import json
from pathlib import Path

from npl_extract.parsers import Block, PageContent, PageRoute, route_page
from npl_extract.pipeline import persist_page_artifacts


def test_routes_native_scan_and_complex_table_pages() -> None:
    assert route_page(PageContent(1, "证券代码 ABC123", [])) is PageRoute.NATIVE
    assert route_page(PageContent(2, "", [])) is PageRoute.OCR
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
    diagnostics = [json.loads(line) for line in (first.run_dir / "page-quality.jsonl").read_text().splitlines()]
    assert [entry["route"] for entry in diagnostics] == ["native", "ocr"]
