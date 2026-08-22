from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

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
