from __future__ import annotations

import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook, load_workbook
from pypdf import PdfWriter

from npl_extract.cli import main
from npl_extract.parsers import Block, PageContent


def test_inspect_command_emits_machine_readable_result(tmp_path: Path, capsys) -> None:
    source = tmp_path / "safe.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    content = BytesIO()
    writer.write(content)
    source.write_bytes(content.getvalue())

    exit_code = main(["inspect", str(source)])

    result = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert result["accepted"]
    assert result["page_count"] == 1


def test_parse_command_writes_evidence_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "safe.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    content = BytesIO()
    writer.write(content)
    source.write_bytes(content.getvalue())

    exit_code = main(["parse", str(source), "--runs-dir", str(tmp_path / "runs")])

    assert exit_code == 0
    assert list((tmp_path / "runs").glob("*/pypdf-6-16-1-all/manifest.json"))


def test_extract_command_routes_an_issuance_result_document(tmp_path: Path, capsys) -> None:
    source = tmp_path / "臻粹不良资产支持证券簿记建档发行结果公告.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    content = BytesIO()
    writer.write(content)
    source.write_bytes(content.getvalue())

    exit_code = main(["extract", str(source), "--runs-dir", str(tmp_path / "runs")])

    assert exit_code == 3
    assert json.loads(capsys.readouterr().out) == []


def test_extract_command_persists_an_issuance_announcement_fact_set(tmp_path: Path, capsys, monkeypatch) -> None:
    source = tmp_path / "臻粹不良资产支持证券发行公告.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    content = BytesIO()
    writer.write(content)
    source.write_bytes(content.getvalue())
    monkeypatch.setattr(
        "npl_extract.cli.parse_native_pdf_isolated",
        lambda *args, **kwargs: [
            PageContent(1, "", [Block("p001:b001", 1, "臻粹不良资产支持证券发行公告", [0, 0, 72, 72])])
        ],
    )

    exit_code = main(["extract", str(source), "--entity-key", "product:test", "--runs-dir", str(tmp_path / "runs")])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output[0]["field_id"] == "asset_full_name"
    manifest = next((tmp_path / "runs").glob("*/pypdf-*-all/manifest.json"))
    facts_path = next((tmp_path / "runs").glob("*/facts/*.jsonl"))
    assert json.loads(facts_path.read_text())["evidence"][0]["artifact_scope"] == json.loads(manifest.read_text())["scope"]


def test_extract_command_persists_an_ocr_issuance_result_fact_set(tmp_path: Path, capsys, monkeypatch) -> None:
    source = tmp_path / "臻粹不良资产支持证券簿记建档发行结果公告.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    content = BytesIO()
    writer.write(content)
    source.write_bytes(content.getvalue())
    monkeypatch.setattr(
        "npl_extract.cli.parse_native_pdf_isolated",
        lambda *args, **kwargs: [
            PageContent(
                1,
                "",
                [
                    Block("p001:b001", 1, "臻粹不良资产支持证券簿记建档发行结果公告", [0, 0, 72, 72]),
                    Block("p001:b009", 1, "证券代码", [0, 0, 72, 72]),
                    Block("p001:b010", 1, "2689075", [0, 0, 72, 72]),
                    Block("p001:b011", 1, "预期到期日", [0, 0, 72, 72]),
                    Block("p001:b012", 1, "2028年2月23日", [0, 0, 72, 72]),
                    Block("p001:b019", 1, "实际发行总额", [0, 0, 72, 72]),
                    Block("p001:b020", 1, "13,200.00万元", [0, 0, 72, 72]),
                ],
                ocr_requested=True,
            )
        ],
    )

    exit_code = main(["extract", str(source), "--native-parser", "docling-ocr", "--runs-dir", str(tmp_path / "runs")])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert {fact["field_id"] for fact in output} == {"security_code", "maturity_date", "tranche_issue_amount"}
    assert next((tmp_path / "runs").glob("*/docling-*-all/manifest.json")).is_file()
    assert next((tmp_path / "runs").glob("*/facts/*.jsonl")).is_file()


def test_extract_command_persists_prospectus_issue_amounts_without_associations(tmp_path: Path, capsys, monkeypatch) -> None:
    source = tmp_path / "臻粹不良资产支持证券发行说明书.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    content = BytesIO()
    writer.write(content)
    source.write_bytes(content.getvalue())
    monkeypatch.setattr(
        "npl_extract.cli.parse_native_pdf_isolated",
        lambda *args, **kwargs: [
            PageContent(
                2,
                "",
                [
                    Block("p002:b001", 2, "证券名称 发行金额（万元）规模占比", None),
                    Block("p002:b002", 2, "优先档 13,200.00 72.53% 过手", None),
                    Block("p002:b003", 2, "次级档 5,000.00 27.47% 过手", None),
                    Block("p002:b004", 2, "总计 18,200.00 100.00% -", None),
                ],
            )
        ],
    )

    exit_code = main(["extract", str(source), "--entity-key", "product:test", "--runs-dir", str(tmp_path / "runs")])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert {(fact["field_id"], fact["value"]) for fact in output} == {
        ("issue_amount_senior", "1.32"),
        ("issue_amount_subordinated", "0.5"),
    }


def test_extract_command_rejects_a_security_key_for_product_facts(tmp_path: Path, capsys, monkeypatch) -> None:
    source = tmp_path / "臻粹不良资产支持证券发行公告.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    content = BytesIO()
    writer.write(content)
    source.write_bytes(content.getvalue())
    monkeypatch.setattr(
        "npl_extract.cli.parse_native_pdf_isolated",
        lambda *args, **kwargs: [
            PageContent(1, "", [Block("p001:b001", 1, "臻粹不良资产支持证券发行公告", [0, 0, 72, 72])])
        ],
    )

    exit_code = main(["extract", str(source), "--entity-key", "security:2689075", "--runs-dir", str(tmp_path / "runs")])

    assert exit_code == 3
    assert json.loads(capsys.readouterr().out) == []


def test_extract_command_projects_prospectus_payment_date_through_association_facts(tmp_path: Path, capsys, monkeypatch) -> None:
    source = tmp_path / "臻粹2026年第二期不良资产支持证券发行说明书.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    content = BytesIO()
    writer.write(content)
    source.write_bytes(content.getvalue())
    associations = tmp_path / "associations.jsonl"
    associations.write_text(
        json.dumps(
            {
                "fact_id": "senior-level",
                "field_id": "tranche_level",
                "entity_key": "security:2689075",
                "status": "disclosed",
                "value": "优先档",
                "evidence": [
                    {
                        "evidence_id": "p001:b005",
                        "artifact_scope": "docling-ocr-all",
                        "document_name": "臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf",
                        "physical_page": 1,
                        "locator": "证券名称",
                        "exact_text": "优先档",
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    monkeypatch.setattr(
        "npl_extract.cli.parse_native_pdf_isolated",
        lambda *args, **kwargs: [
            PageContent(
                2,
                "",
                [
                    Block("p002:b028", 2, "资产支持证券的第一个支付日是 2026 年 5 月 23 日", None),
                    Block("p002:b011", 2, "方式 利率类型 预期到期日 法定到期日 评级", None),
                    Block("p002:b012", 2, "（中债资信/中诚信）", None),
                    Block("p002:b013", 2, "优先档 13,200.00 72.53% 过手 固定利率 2028/2/23 2032/4/23 AAAsf/AAAsf", None),
                ],
            )
        ],
    )

    exit_code = main(
        [
            "extract",
            str(source),
            "--entity-key",
            "product:test",
            "--association-facts",
            str(associations),
            "--runs-dir",
            str(tmp_path / "runs"),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert {fact["field_id"] for fact in output} == {"first_interest_payment_date", "issue_rating"}
    assert {fact["entity_key"] for fact in output} == {"security:2689075"}


def test_extract_trustee_command_rejects_a_product_key_for_report_facts(tmp_path: Path, capsys, monkeypatch) -> None:
    source = tmp_path / "受托报告.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    content = BytesIO()
    writer.write(content)
    source.write_bytes(content.getvalue())
    monkeypatch.setattr(
        "npl_extract.cli.extract_trustee_report_facts",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("extractor must not run")),
    )

    exit_code = main(["extract-trustee", str(source), "--entity-key", "product:test", "--runs-dir", str(tmp_path / "runs")])

    assert exit_code == 3
    assert json.loads(capsys.readouterr().out) == []


def test_export_command_projects_persisted_facts_to_a_template(tmp_path: Path, capsys) -> None:
    template = tmp_path / "template.xlsx"
    workbook = Workbook()
    workbook.active["A1"] = "资产全称"
    workbook.save(template)
    facts = tmp_path / "facts.jsonl"
    facts.write_text(
        json.dumps(
            {
                "fact_id": "asset-name",
                "field_id": "asset_full_name",
                "entity_key": "product:test",
                "status": "disclosed",
                "value": "臻粹不良资产支持证券",
                "evidence": [
                    {
                        "evidence_id": "p001:b001",
                        "artifact_scope": "pypdf-all",
                        "document_name": "发行公告.pdf",
                        "physical_page": 1,
                        "locator": "公告标题",
                        "exact_text": "臻粹不良资产支持证券发行公告",
                    }
                ],
                "effective_at": None,
                "rule_version": None,
                "derived_inputs": [],
                "confirmed": False,
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    output = tmp_path / "export.xlsx"

    exit_code = main(["export", "--template", str(template), "--facts", str(facts), "--output", str(output)])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["fact_count"] == 1
    assert load_workbook(output)["product_test"]["B1"].value == "臻粹不良资产支持证券"


def test_export_command_rejects_a_jsonl_fact_with_the_wrong_entity_grain(tmp_path: Path, capsys) -> None:
    template = tmp_path / "template.xlsx"
    Workbook().save(template)
    facts = tmp_path / "facts.jsonl"
    facts.write_text(
        json.dumps(
            {
                "fact_id": "asset-name",
                "field_id": "asset_full_name",
                "entity_key": "security:2689075",
                "status": "disclosed",
                "value": "臻粹不良资产支持证券",
                "evidence": [
                    {
                        "evidence_id": "p001:b001",
                        "artifact_scope": "pypdf-all",
                        "document_name": "发行公告.pdf",
                        "physical_page": 1,
                        "locator": "公告标题",
                        "exact_text": "臻粹不良资产支持证券发行公告",
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n"
    )

    exit_code = main(["export", "--template", str(template), "--facts", str(facts), "--output", str(tmp_path / "export.xlsx")])

    assert exit_code == 2
    assert "product key" in json.loads(capsys.readouterr().out)["error"]


def test_review_command_appends_an_accepted_fact_decision(tmp_path: Path, capsys) -> None:
    document_sha256 = "a" * 64
    content = (
        json.dumps(
            {
                "fact_id": "asset-name",
                "field_id": "asset_full_name",
                "entity_key": "product:test",
                "status": "disclosed",
                "value": "臻粹不良资产支持证券",
                "evidence": [
                    {
                        "evidence_id": "p001:b001",
                        "artifact_scope": "pypdf-all",
                        "document_name": "发行公告.pdf",
                        "physical_page": 1,
                        "locator": "公告标题",
                        "exact_text": "臻粹不良资产支持证券发行公告",
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    runs_dir = tmp_path / "runs"
    candidates = runs_dir / document_sha256 / "facts" / f"{sha256(content.encode()).hexdigest()}.jsonl"
    candidates.parent.mkdir(parents=True)
    candidates.write_text(content)

    exit_code = main(
        [
            "review",
            "--document-sha256",
            document_sha256,
            "--facts",
            str(candidates),
            "--fact-id",
            "asset-name",
            "--action",
            "accept",
            "--decision-id",
            "review-001",
            "--reviewer-id",
            "business-owner:alice",
            "--reason-code",
            "VALUE_AND_EVIDENCE_CONFIRMED",
            "--runs-dir",
            str(runs_dir),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["action"] == "accept"
    assert output["resolved_fact"]["confirmed"] is True
    assert (runs_dir / document_sha256 / "reviews" / "review-001.json").is_file()


def test_review_command_rejects_a_candidate_from_another_document(tmp_path: Path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    candidates = runs_dir / ("b" * 64) / "facts" / f"{sha256(b'').hexdigest()}.jsonl"
    candidates.parent.mkdir(parents=True)
    candidates.write_text("")

    exit_code = main(
        [
            "review",
            "--document-sha256",
            "a" * 64,
            "--facts",
            str(candidates),
            "--fact-id",
            "asset-name",
            "--action",
            "accept",
            "--decision-id",
            "review-002",
            "--reviewer-id",
            "business-owner:alice",
            "--reason-code",
            "VALUE_AND_EVIDENCE_CONFIRMED",
            "--runs-dir",
            str(runs_dir),
        ]
    )

    assert exit_code == 2
    assert "canonical" in json.loads(capsys.readouterr().out)["error"]


def test_review_command_rejects_a_tampered_candidate_artifact(tmp_path: Path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    candidates = runs_dir / ("a" * 64) / "facts" / f"{'b' * 64}.jsonl"
    candidates.parent.mkdir(parents=True)
    candidates.write_text("")

    exit_code = main(
        [
            "review",
            "--document-sha256",
            "a" * 64,
            "--facts",
            str(candidates),
            "--fact-id",
            "asset-name",
            "--action",
            "accept",
            "--decision-id",
            "review-003",
            "--reviewer-id",
            "business-owner:alice",
            "--reason-code",
            "VALUE_AND_EVIDENCE_CONFIRMED",
            "--runs-dir",
            str(runs_dir),
        ]
    )

    assert exit_code == 2
    assert "content-addressed" in json.loads(capsys.readouterr().out)["error"]
