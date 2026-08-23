from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from npl_extract.contracts import EvidenceRef, ExtractionFact, FactStatus
from npl_extract.extract import (
    extract_issuance_announcement_facts,
    extract_issuance_result_ocr_facts,
    extract_rating_report_facts,
)
from pathlib import Path

import pytest
from pypdf import PdfWriter

from npl_extract.parsers import Block, PageContent, PageRoute, PypdfNativeParser, Table, TableCell, parse_native_pdf_isolated, route_page, tables_from_ppstructure_result
from npl_extract.pipeline import persist_facts, persist_page_artifacts, stage_verified_pdf


def test_routes_native_scan_and_complex_table_pages() -> None:
    assert route_page(PageContent(1, "证券代码 ABC123", [])) is PageRoute.NATIVE
    assert route_page(PageContent(2, "", [])) is PageRoute.OCR
    assert route_page(PageContent(2, "A", [])) is PageRoute.OCR
    assert route_page(PageContent(3, "表格文字", [], has_complex_table=True)) is PageRoute.HYBRID
    assert route_page(PageContent(4, "OCR 后的充足文本内容", [], ocr_requested=True)) is PageRoute.NATIVE


def test_persists_parser_owned_table_cells_with_coordinates(tmp_path: Path) -> None:
    page = PageContent(
        112,
        "现金流归集表",
        tables=[
            Table(
                table_id="p112:t001",
                physical_page=112,
                cells=[
                    TableCell("p112:t001:r000:c000", 112, "p112:t001", 0, 0, "期数", [10, 20, 30, 40]),
                    TableCell("p112:t001:r001:c000", 112, "p112:t001", 1, 0, "2026 年 1 月", [10, 40, 30, 60]),
                ],
            )
        ],
    )

    persisted = persist_page_artifacts("e" * 64, [page], tmp_path)

    assert route_page(page) is PageRoute.HYBRID
    assert json.loads((persisted.run_dir / "tables.jsonl").read_text()) == {
        "table_id": "p112:t001",
        "physical_page": 112,
        "cells": [
            {"evidence_id": "p112:t001:r000:c000", "physical_page": 112, "table_id": "p112:t001", "row": 0, "column": 0, "exact_text": "期数", "bbox": [10, 20, 30, 40]},
            {"evidence_id": "p112:t001:r001:c000", "physical_page": 112, "table_id": "p112:t001", "row": 1, "column": 0, "exact_text": "2026 年 1 月", "bbox": [10, 40, 30, 60]},
        ],
    }


def test_normalizes_ppstructure_cells_to_the_table_artifact_contract() -> None:
    tables = tables_from_ppstructure_result(
        {"res": {"table_res_list": [{
            "pred_html": "<table><tr><td>期数</td><td>预计回收金额（万元）</td></tr><tr><td>2026 年 1 月</td><td>160.70</td></tr></table>",
            "table_ocr_pred": {"rec_texts": ["期数", "预计回收金额（万元）", "2026 年 1 月", "160.70"], "rec_boxes": [[0, 0, 1, 1], [1, 0, 2, 1], [0, 1, 1, 2], [1, 1, 2, 2]]},
        }]}},
        physical_page=112,
    )

    assert tables == [Table("p112:t001", 112, [
        TableCell("p112:t001:r000:c000", 112, "p112:t001", 0, 0, "期数", [0, 0, 1, 1]),
        TableCell("p112:t001:r000:c001", 112, "p112:t001", 0, 1, "预计回收金额（万元）", [1, 0, 2, 1]),
        TableCell("p112:t001:r001:c000", 112, "p112:t001", 1, 0, "2026 年 1 月", [0, 1, 1, 2]),
        TableCell("p112:t001:r001:c001", 112, "p112:t001", 1, 1, "160.70", [1, 1, 2, 2]),
    ])]


def test_extracts_product_identity_cutoff_and_issue_total_from_issuance_announcement() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block(
                    "p001:b001",
                    1,
                    "臻粹 2026 年第二期不良资产支持证券 发行公告\n发行规模为 182,000,000.00 元的臻粹 2026 年第二期不良资产支持证券",
                    [0, 0, 72, 72],
                )
            ],
        ),
        PageContent(
            2,
            "",
            [
                Block("p002:b001", 2, "初始起算日 2026 年 1 月 26 日零点", [0, 0, 72, 72])
            ],
        ),
    ]

    facts = extract_issuance_announcement_facts(
        pages, "臻粹2026年第二期不良资产支持证券发行公告.pdf", "product:test", "pypdf-all"
    )

    assert {(fact.field_id, fact.value) for fact in facts} == {
        ("asset_full_name", "臻粹2026年第二期不良资产支持证券"),
        ("initial_cutoff_date", "2026-01-26"),
        ("issue_amount_all_tranches", "1.82"),
    }
    assert all(fact.status is FactStatus.DISCLOSED for fact in facts)
    assert {fact.evidence[0].physical_page for fact in facts} == {1, 2}


def test_extracts_security_records_from_ocr_issuance_result_tables() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "臻粹 2026 年第二期不良资产支持证券簿记建档发行结果公告", [0, 0, 72, 72]),
                Block("p001:b009", 1, "证券代码", [0, 0, 72, 72]),
                Block("p001:b010", 1, "2689075", [0, 0, 72, 72]),
                Block("p001:b011", 1, "预期到期日", [0, 0, 72, 72]),
                Block("p001:b012", 1, "2028年2月23日", [0, 0, 72, 72]),
                Block("p001:b019", 1, "实际发行总额", [0, 0, 72, 72]),
                Block("p001:b020", 1, "13,200.00万元", [0, 0, 72, 72]),
            ],
            ocr_requested=True,
        ),
        PageContent(
            2,
            "",
            [
                Block("p002:b007", 2, "证券代码", [0, 0, 72, 72]),
                Block("p002:b008", 2, "2689076", [0, 0, 72, 72]),
                Block("p002:b009", 2, "预期到期日", [0, 0, 72, 72]),
                Block("p002:b010", 2, "2029年4月23日", [0, 0, 72, 72]),
                Block("p002:b018", 2, "实际发行总额", [0, 0, 72, 72]),
                Block("p002:b019", 2, "5,000.00万元", [0, 0, 72, 72]),
            ],
            ocr_requested=True,
        ),
    ]

    facts = extract_issuance_result_ocr_facts(
        pages, "臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf", "paddleocr-page"
    )

    assert {(fact.field_id, fact.entity_key, fact.value) for fact in facts} == {
        ("security_code", "security:2689075", "2689075"),
        ("maturity_date", "security:2689075", "2028-02-23"),
        ("tranche_issue_amount", "security:2689075", "1.32"),
        ("security_code", "security:2689076", "2689076"),
        ("maturity_date", "security:2689076", "2029-04-23"),
        ("tranche_issue_amount", "security:2689076", "0.5"),
    }
    assert all(fact.status is FactStatus.DISCLOSED for fact in facts)
    assert all(fact.evidence[0].evidence_id == "p001:b001" for fact in facts)


def test_ocr_issuance_result_rejects_duplicate_security_codes_on_one_table() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "臻粹 2026 年第二期不良资产支持证券簿记建档发行结果公告", [0, 0, 72, 72]),
                Block("p001:b009", 1, "证券代码", [0, 0, 72, 72]),
                Block("p001:b010", 1, "2689075", [0, 0, 72, 72]),
                Block("p001:b011", 1, "证券代码", [0, 0, 72, 72]),
                Block("p001:b012", 1, "2689076", [0, 0, 72, 72]),
                Block("p001:b013", 1, "预期到期日", [0, 0, 72, 72]),
                Block("p001:b014", 1, "2028年2月23日", [0, 0, 72, 72]),
                Block("p001:b015", 1, "实际发行总额", [0, 0, 72, 72]),
                Block("p001:b016", 1, "13,200.00万元", [0, 0, 72, 72]),
            ],
            ocr_requested=True,
        )
    ]

    facts = extract_issuance_result_ocr_facts(
        pages, "臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf", "paddleocr-page"
    )

    assert facts == []


def test_ocr_issuance_result_requires_the_first_ocr_block_to_be_the_title() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b000", 1, "正文引用", [0, 0, 72, 72]),
                Block("p001:b001", 1, "臻粹 2026 年第二期不良资产支持证券簿记建档发行结果公告", [0, 0, 72, 72]),
                Block("p001:b009", 1, "证券代码", [0, 0, 72, 72]),
                Block("p001:b010", 1, "2689075", [0, 0, 72, 72]),
                Block("p001:b011", 1, "预期到期日", [0, 0, 72, 72]),
                Block("p001:b012", 1, "2028年2月23日", [0, 0, 72, 72]),
                Block("p001:b019", 1, "实际发行总额", [0, 0, 72, 72]),
                Block("p001:b020", 1, "13,200.00万元", [0, 0, 72, 72]),
            ],
            ocr_requested=True,
        )
    ]

    facts = extract_issuance_result_ocr_facts(
        pages, "臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf", "paddleocr-page"
    )

    assert facts == []


def test_ocr_issuance_result_rejects_a_document_with_an_incomplete_tranche_page() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "臻粹 2026 年第二期不良资产支持证券簿记建档发行结果公告", [0, 0, 72, 72]),
                Block("p001:b009", 1, "证券代码", [0, 0, 72, 72]),
                Block("p001:b010", 1, "2689075", [0, 0, 72, 72]),
                Block("p001:b011", 1, "预期到期日", [0, 0, 72, 72]),
                Block("p001:b012", 1, "2028年2月23日", [0, 0, 72, 72]),
                Block("p001:b019", 1, "实际发行总额", [0, 0, 72, 72]),
                Block("p001:b020", 1, "13,200.00万元", [0, 0, 72, 72]),
            ],
            ocr_requested=True,
        ),
        PageContent(
            2,
            "",
            [
                Block("p002:b007", 2, "证券代码", [0, 0, 72, 72]),
                Block("p002:b008", 2, "2689076", [0, 0, 72, 72]),
                Block("p002:b009", 2, "预期到期日", [0, 0, 72, 72]),
                Block("p002:b010", 2, "2029年4月23日", [0, 0, 72, 72]),
            ],
            ocr_requested=True,
        ),
    ]

    facts = extract_issuance_result_ocr_facts(
        pages, "臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf", "paddleocr-page"
    )

    assert facts == []


def test_ocr_issuance_result_rejects_a_trailing_unpaired_table_label() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "臻粹 2026 年第二期不良资产支持证券簿记建档发行结果公告", [0, 0, 72, 72]),
                Block("p001:b009", 1, "证券代码", [0, 0, 72, 72]),
                Block("p001:b010", 1, "2689075", [0, 0, 72, 72]),
                Block("p001:b011", 1, "预期到期日", [0, 0, 72, 72]),
                Block("p001:b012", 1, "2028年2月23日", [0, 0, 72, 72]),
                Block("p001:b019", 1, "实际发行总额", [0, 0, 72, 72]),
                Block("p001:b020", 1, "13,200.00万元", [0, 0, 72, 72]),
            ],
            ocr_requested=True,
        ),
        PageContent(2, "", [Block("p002:b024", 2, "实际发行总额", [0, 0, 72, 72])], ocr_requested=True),
    ]

    facts = extract_issuance_result_ocr_facts(
        pages, "臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf", "paddleocr-page"
    )

    assert facts == []


def test_extracts_initial_pool_balance_from_rating_report() -> None:
    pages = [
        PageContent(
            4,
            "",
            [
                Block("p004:b017", 4, "资产池特征（于初始起算日）", [0, 0, 72, 72]),
                Block("p004:b019", 4, "资产池未偿本息费余额 314,258.72 万元", [0, 0, 72, 72]),
            ],
        )
    ]

    facts = extract_rating_report_facts(
        pages, "臻粹2026年第二期不良资产支持证券信用评级报告.pdf", "product:test", "pypdf-all"
    )

    assert [(fact.field_id, fact.value) for fact in facts] == [
        ("initial_pool_outstanding_principal_interest_fees", "3142587200")
    ]
    assert [evidence.evidence_id for evidence in facts[0].evidence] == ["p004:b017", "p004:b019"]


def test_rating_report_rejects_multiple_initial_pool_balances() -> None:
    pages = [
        PageContent(
            4,
            "",
            [
                Block("p004:b017", 4, "资产池特征（于初始起算日）", [0, 0, 72, 72]),
                Block("p004:b019", 4, "资产池未偿本息费余额 314,258.72 万元", [0, 0, 72, 72]),
                Block("p004:b020", 4, "资产池未偿本息费余额 1 万元", [0, 0, 72, 72]),
            ],
        )
    ]

    facts = extract_rating_report_facts(
        pages, "臻粹2026年第二期不良资产支持证券信用评级报告.pdf", "product:test", "pypdf-all"
    )

    assert facts == []


def test_rating_report_skips_a_pure_scan_page() -> None:
    facts = extract_rating_report_facts(
        [
            PageContent(
                4,
                "OCR 后的文本",
                [
                    Block("p004:b017", 4, "资产池特征（于初始起算日）", [0, 0, 72, 72]),
                    Block("p004:b019", 4, "资产池未偿本息费余额 314,258.72 万元", [0, 0, 72, 72]),
                ],
                ocr_requested=True,
            )
        ],
        "臻粹2026年第二期不良资产支持证券信用评级报告.pdf",
        "product:test",
        "pypdf-all",
    )

    assert facts == []


def test_issuance_full_name_comes_from_the_announcement_title_not_body_reference() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "本期不良资产支持证券发行规模为 1 元", [0, 0, 72, 72]),
                Block("p001:b002", 1, "臻粹 2026 年第二期不良资产支持证券 发行公告", [0, 0, 72, 72]),
            ],
        )
    ]

    facts = extract_issuance_announcement_facts(
        pages, "臻粹2026年第二期不良资产支持证券发行公告.pdf", "product:test", "pypdf-all"
    )

    name = next(fact for fact in facts if fact.field_id == "asset_full_name")
    assert name.value == "臻粹2026年第二期不良资产支持证券"
    assert name.evidence[0].evidence_id == "p001:b002"


def test_issuance_total_requires_the_current_product_title_context() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "历史产品发行规模为 999,000,000.00 元", [0, 0, 72, 72]),
                Block(
                    "p001:b002",
                    1,
                    "臻粹 2026 年第二期不良资产支持证券 发行公告\n发行规模为 182,000,000.00 元的臻粹 2026 年第二期不良资产支持证券",
                    [0, 0, 72, 72],
                ),
            ],
        )
    ]

    facts = extract_issuance_announcement_facts(
        pages, "臻粹2026年第二期不良资产支持证券发行公告.pdf", "product:test", "pypdf-all"
    )

    amount = next(fact for fact in facts if fact.field_id == "issue_amount_all_tranches")
    assert amount.value == "1.82"
    assert amount.evidence[0].evidence_id == "p001:b002"


def test_issuance_rejects_ambiguous_or_comparative_issue_amounts() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "臻粹 2026 年第二期不良资产支持证券发行公告", [0, 0, 72, 72]),
                Block(
                    "p001:b002",
                    1,
                    "历史产品发行规模为 999,000,000.00 元；与臻粹 2026 年第二期不良资产支持证券比较",
                    [0, 0, 72, 72],
                ),
                Block(
                    "p001:b003",
                    1,
                    "发行规模为 182,000,000.00 元的臻粹 2026 年第二期不良资产支持证券；发行规模为 1 元的臻粹 2026 年第二期不良资产支持证券",
                    [0, 0, 72, 72],
                ),
            ],
        )
    ]

    facts = extract_issuance_announcement_facts(
        pages, "臻粹2026年第二期不良资产支持证券发行公告.pdf", "product:test", "pypdf-all"
    )

    assert all(fact.field_id != "issue_amount_all_tranches" for fact in facts)


def test_issuance_rejects_issue_amount_candidates_across_blocks() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "臻粹 2026 年第二期不良资产支持证券发行公告", [0, 0, 72, 72]),
                Block(
                    "p001:b002",
                    1,
                    "发行规模为 182,000,000.00 元的臻粹 2026 年第二期不良资产支持证券",
                    [0, 0, 72, 72],
                ),
            ],
        ),
        PageContent(
            2,
            "",
            [
                Block(
                    "p002:b001",
                    2,
                    "发行规模为 1 元的臻粹 2026 年第二期不良资产支持证券",
                    [0, 0, 72, 72],
                )
            ],
        ),
    ]

    facts = extract_issuance_announcement_facts(
        pages, "臻粹2026年第二期不良资产支持证券发行公告.pdf", "product:test", "pypdf-all"
    )

    assert all(fact.field_id != "issue_amount_all_tranches" for fact in facts)


def test_issuance_rejects_multiple_initial_cutoff_dates() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "臻粹 2026 年第二期不良资产支持证券发行公告", [0, 0, 72, 72]),
                Block("p001:b002", 1, "历史产品初始起算日 2025 年 1 月 26 日", [0, 0, 72, 72]),
            ],
        ),
        PageContent(
            2,
            "",
            [Block("p002:b001", 2, "初始起算日 2026 年 1 月 26 日", [0, 0, 72, 72])],
        ),
    ]

    facts = extract_issuance_announcement_facts(
        pages, "臻粹2026年第二期不良资产支持证券发行公告.pdf", "product:test", "pypdf-all"
    )

    assert all(fact.field_id != "initial_cutoff_date" for fact in facts)


def test_issuance_rejects_multiple_initial_cutoff_dates_in_one_block() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "臻粹 2026 年第二期不良资产支持证券发行公告", [0, 0, 72, 72]),
                Block(
                    "p001:b002",
                    1,
                    "历史产品初始起算日 2025 年 1 月 26 日；本期初始起算日 2026 年 1 月 26 日",
                    [0, 0, 72, 72],
                ),
            ],
        )
    ]

    facts = extract_issuance_announcement_facts(
        pages, "臻粹2026年第二期不良资产支持证券发行公告.pdf", "product:test", "pypdf-all"
    )

    assert all(fact.field_id != "initial_cutoff_date" for fact in facts)


def test_issuance_rejects_split_title_referenced_after_the_cover_page() -> None:
    pages = [
        PageContent(
            2,
            "",
            [
                Block("p002:b001", 2, "臻粹 2026 年第二期不良资产支持证券", [0, 0, 72, 72]),
                Block("p002:b002", 2, "发行公告", [0, 0, 72, 72]),
            ],
        )
    ]

    facts = extract_issuance_announcement_facts(
        pages, "臻粹2026年第二期不良资产支持证券发行公告.pdf", "product:test", "pypdf-all"
    )

    assert all(fact.field_id != "asset_full_name" for fact in facts)


def test_issuance_title_and_issue_total_support_adjacent_pypdf_blocks() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "臻粹 2026 年第二期不良资产支持证券 ", [0, 0, 72, 72]),
                Block("p001:b002", 1, "发行公告（摘要）", [0, 0, 72, 72]),
                Block("p001:b003", 1, "发行规模为 182,000,000.00 元的臻粹", [0, 0, 72, 72]),
                Block("p001:b004", 1, "2026 年第二期不良资产支持证券（以下简称本期证券）", [0, 0, 72, 72]),
            ],
        )
    ]

    facts = extract_issuance_announcement_facts(
        pages, "臻粹2026年第二期不良资产支持证券发行公告.pdf", "product:test", "pypdf-all"
    )

    assert {(fact.field_id, fact.value) for fact in facts} == {
        ("asset_full_name", "臻粹2026年第二期不良资产支持证券"),
        ("issue_amount_all_tranches", "1.82"),
    }
    name = next(fact for fact in facts if fact.field_id == "asset_full_name")
    assert [evidence.evidence_id for evidence in name.evidence] == ["p001:b001", "p001:b002"]
    amount = next(fact for fact in facts if fact.field_id == "issue_amount_all_tranches")
    assert [evidence.evidence_id for evidence in amount.evidence] == ["p001:b003", "p001:b004"]


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
    assert [entry["ocr_requested"] for entry in diagnostics] == [False, False]
    assert [entry["route_basis"] for entry in diagnostics] == ["returned_text", "returned_text"]


def test_staged_pdf_rejects_source_bytes_changed_after_intake(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"first")
    expected_hash = sha256(b"first").hexdigest()
    source.write_bytes(b"changed")

    with pytest.raises(ValueError, match="changed"):
        stage_verified_pdf(source, expected_hash, tmp_path)


def test_repairs_an_incomplete_artifact_run_instead_of_reusing_it(tmp_path: Path) -> None:
    pages = [PageContent(1, "证券代码 ABC123", [Block("p001:b001", 1, "证券代码 ABC123", [0, 0, 72, 12])])]
    first = persist_page_artifacts("b" * 64, pages, tmp_path)
    (first.run_dir / "blocks.jsonl").unlink()

    repaired = persist_page_artifacts("b" * 64, pages, tmp_path)

    assert not repaired.reused
    assert (repaired.run_dir / "blocks.jsonl").is_file()


def test_repairs_a_run_created_by_the_pre_table_pipeline_version(tmp_path: Path) -> None:
    pages = [PageContent(1, "证券代码 ABC123", [])]
    first = persist_page_artifacts("c" * 64, pages, tmp_path)
    manifest_path = first.run_dir / "manifest.json"
    manifest_path.write_text('{"document_sha256":"' + "c" * 64 + '","pipeline_version":"v3","scope":"all"}')

    repaired = persist_page_artifacts("c" * 64, pages, tmp_path)

    assert not repaired.reused


def test_page_scope_does_not_reuse_a_whole_document_artifact(tmp_path: Path) -> None:
    pages = [PageContent(1, "证券代码 ABC123", [])]
    whole = persist_page_artifacts("f" * 64, pages, tmp_path)
    partial = persist_page_artifacts("f" * 64, pages, tmp_path, scope="docling-ocr-pages-1-1")

    assert whole.run_dir != partial.run_dir
    assert not partial.reused


def test_parser_scope_does_not_reuse_another_engine_artifact(tmp_path: Path) -> None:
    pages = [PageContent(1, "证券代码 ABC123", [])]
    pypdf = persist_page_artifacts("9" * 64, pages, tmp_path, scope="parser-pages-1-1", parser_identity="pypdf-6-16-1")
    docling = persist_page_artifacts("9" * 64, pages, tmp_path, scope="parser-pages-1-1", parser_identity="docling-2-121-0-native-no-table")

    assert pypdf.run_dir == docling.run_dir
    assert not docling.reused
    assert json.loads((docling.run_dir / "manifest.json").read_text())["parser_identity"] == "docling-2-121-0-native-no-table"


def test_concurrent_writers_leave_a_complete_artifact_run(tmp_path: Path) -> None:
    one_page = [PageContent(1, "证券代码 ABC123", [Block("p001:b001", 1, "证券代码 ABC123", [0, 0, 72, 12])])]
    two_pages = one_page + [PageContent(2, "证券名称 DEF456", [Block("p002:b001", 2, "证券名称 DEF456", [0, 0, 72, 12])])]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pages: persist_page_artifacts("d" * 64, pages, tmp_path), [one_page, two_pages]))

    assert any(not result.reused for result in results)
    run_dir = tmp_path / ("d" * 64) / "pypdf-all"
    diagnostics = (run_dir / "page-quality.jsonl").read_text().splitlines()
    blocks = (run_dir / "blocks.jsonl").read_text().splitlines()
    assert len(diagnostics) == len(blocks)


def test_native_parser_preserves_page_text_and_evidence_id(tmp_path: Path) -> None:
    source = tmp_path / "native.pdf"
    source.write_bytes(_text_pdf("Security ABC123"))

    pages = PypdfNativeParser().parse(source)

    assert pages[0].physical_page == 1
    assert "ABC123" in pages[0].native_text
    assert pages[0].blocks[0].evidence_id == "p001:b001"
    assert pages[0].blocks[0].bbox is None


def test_isolated_native_parser_preserves_page_text(tmp_path: Path) -> None:
    source = tmp_path / "native.pdf"
    source.write_bytes(_text_pdf("Security ABC123"))

    pages = parse_native_pdf_isolated(source, timeout_seconds=5)

    assert "ABC123" in pages[0].native_text


def test_isolated_parser_honors_page_range(tmp_path: Path) -> None:
    source = tmp_path / "native.pdf"
    source.write_bytes(_two_page_text_pdf())

    pages = parse_native_pdf_isolated(source, page_range=(2, 2), timeout_seconds=5)

    assert [page.physical_page for page in pages] == [2]


def test_isolated_parser_rechecks_the_staged_input_hash(tmp_path: Path) -> None:
    source = tmp_path / "native.pdf"
    source.write_bytes(_text_pdf("Security ABC123"))

    with pytest.raises(RuntimeError, match="PARSER_INPUT_CHANGED"):
        parse_native_pdf_isolated(source, expected_sha256="0" * 64, timeout_seconds=5)


def test_docling_parser_keeps_bbox_for_a_native_page(tmp_path: Path) -> None:
    pytest.importorskip("docling")
    source = tmp_path / "native.pdf"
    source.write_bytes(_text_pdf("Security ABC123"))

    pages = parse_native_pdf_isolated(source, parser="docling", timeout_seconds=30)

    assert "Security" in pages[0].native_text
    assert pages[0].blocks[0].bbox is not None
    assert pages[0].page_width == 72
    assert pages[0].page_height == 72


@pytest.mark.skipif(os.getenv("RUN_REAL_PARSER_TESTS") != "1", reason="real Docling OCR is opt-in")
def test_docling_ocr_option_reaches_the_worker(tmp_path: Path) -> None:
    source = tmp_path / "native.pdf"
    source.write_bytes(_text_pdf("Security ABC123"))

    pages = parse_native_pdf_isolated(source, parser="docling-ocr", timeout_seconds=30)

    assert pages[0].blocks[0].bbox is not None
    assert pages[0].ocr_requested


def test_parser_worker_error_is_clear(tmp_path: Path) -> None:
    source = tmp_path / "native.pdf"
    source.write_bytes(_text_pdf("Security ABC123"))

    with pytest.raises(RuntimeError, match="PARSER_FAILED"):
        parse_native_pdf_isolated(source, parser="unknown", timeout_seconds=5)


def test_persisted_facts_refuse_a_conflicting_retry(tmp_path: Path) -> None:
    fact = ExtractionFact(
        fact_id="disclosed:date:p001:b001",
        field_id="latest_report_date",
        entity_key="report:test",
        status=FactStatus.DISCLOSED,
        value="2026-08-17",
        evidence=[EvidenceRef(evidence_id="p001:b001", artifact_scope="pypdf-all", document_name="报告.pdf", physical_page=1, locator="报告日期", exact_text="2026年8月17日")],
    )
    first = persist_facts("e" * 64, [fact], tmp_path)
    second = persist_facts("e" * 64, [fact], tmp_path)

    assert not first.reused
    assert second.reused
    assert first.path.parent.name == "facts"


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


def _two_page_text_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
