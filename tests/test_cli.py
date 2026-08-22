from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter

from npl_extract.cli import main


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
    assert list((tmp_path / "runs").glob("*/manifest.json"))
