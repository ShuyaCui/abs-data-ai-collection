from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import subprocess

import pytest

from npl_extract import harness_bridge


ROOT = Path(__file__).parents[1]
WORKER = ROOT / "src" / "npl_extract" / "harness_bridge.py"
SHA256 = "a" * 64


def _call(tmp_path: Path, operation: str, payload: dict[str, object]) -> dict[str, object]:
    result = subprocess.run(
        [".venv/bin/python", str(WORKER), operation],
        cwd=ROOT,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
        env={"NPL_RUNS_DIR": str(tmp_path)},
    )
    return json.loads(result.stdout)


def _persist_candidate(tmp_path: Path, fact: dict[str, object]) -> str:
    content = json.dumps(fact, ensure_ascii=False) + "\n"
    path = tmp_path / SHA256 / "facts" / f"{sha256(content.encode()).hexdigest()}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    assert isinstance(fact["fact_id"], str)
    return fact["fact_id"]


def test_harness_bridge_retrieves_only_hash_scoped_evidence(tmp_path: Path) -> None:
    scope = tmp_path / SHA256 / "pypdf-all"
    scope.mkdir(parents=True)
    (scope / "blocks.jsonl").write_text(json.dumps({"evidence_id": "block:1", "physical_page": 1, "exact_text": "证据文本"}) + "\n")

    response = _call(tmp_path, "retrieve_evidence", {"document_sha256": SHA256, "scope": "pypdf-all", "evidence_id": "block:1"})

    assert response == {
        "operation": "retrieve_evidence",
        "status": "ok",
        "result": {"scope": "pypdf-all", "evidence": {"evidence_id": "block:1", "physical_page": 1, "exact_text": "证据文本"}},
    }


def test_harness_bridge_truncates_an_approved_evidence_excerpt(tmp_path: Path) -> None:
    scope = tmp_path / SHA256 / "pypdf-all"
    scope.mkdir(parents=True)
    (scope / "blocks.jsonl").write_text(json.dumps({"evidence_id": "block:1", "physical_page": 1, "exact_text": "12345"}) + "\n")

    response = _call(tmp_path, "retrieve_evidence", {"document_sha256": SHA256, "scope": "pypdf-all", "evidence_id": "block:1", "max_text_chars": 3})

    assert response["result"]["evidence"] == {"evidence_id": "block:1", "physical_page": 1, "exact_text": "123", "truncated": True}


def test_harness_bridge_caps_total_fact_evidence_text_per_response() -> None:
    facts = [{"evidence": [{"exact_text": "1234"}, {"exact_text": "5678"}]}]

    result = harness_bridge._externalize_facts(facts, {"max_text_chars": 5})

    assert result == [{"evidence": [{"exact_text": "1234"}, {"exact_text": "5", "truncated": True}]}]


def test_harness_bridge_rejects_a_staged_pdf_with_the_wrong_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = tmp_path / SHA256
    run_dir.mkdir()
    (run_dir / "input.pdf").write_bytes(b"tampered")
    monkeypatch.setenv("NPL_RUNS_DIR", str(tmp_path))

    with pytest.raises(ValueError, match="staged PDF hash mismatch"):
        harness_bridge.extract_field_facts(
            {"document_sha256": SHA256, "entity_key": "product:test", "native_parser": "pypdf"}
        )


def test_harness_bridge_redacts_extractor_evidence_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    content = b"verified"
    document_hash = sha256(content).hexdigest()
    run_dir = tmp_path / document_hash
    run_dir.mkdir()
    (run_dir / "input.pdf").write_bytes(content)
    (run_dir / "source.json").write_text(json.dumps({"document_name": "可信报告.pdf"}))
    monkeypatch.setenv("NPL_RUNS_DIR", str(tmp_path))
    monkeypatch.setattr(
        harness_bridge,
        "cli_main",
        lambda _args: (print(json.dumps([{"fact_id": "fact:1", "evidence": [{"exact_text": "不可外发全文"}]}])), 0)[1],
    )

    response = harness_bridge.extract_field_facts(
        {"document_sha256": document_hash, "entity_key": "product:test", "native_parser": "pypdf", "redact_evidence_text": True}
    )

    assert response["result"][0]["evidence"][0]["exact_text"] == ""


def test_harness_bridge_validates_facts_against_parser_owned_evidence(tmp_path: Path) -> None:
    scope = tmp_path / SHA256 / "pypdf-all"
    scope.mkdir(parents=True)
    (scope / "blocks.jsonl").write_text(json.dumps({"evidence_id": "block:1", "physical_page": 1, "exact_text": "2689075"}) + "\n")
    (tmp_path / SHA256 / "source.json").write_text(json.dumps({"document_name": "可信报告.pdf"}))
    fact = {
        "fact_id": "fact:1",
        "field_id": "security_code",
        "entity_key": "security:2689075",
        "status": "disclosed",
        "value": "2689075",
        "evidence": [{"evidence_id": "block:1", "artifact_scope": "pypdf-all", "document_name": "sample.pdf", "physical_page": 1, "locator": "row", "exact_text": "2689075"}],
    }

    fact_id = _persist_candidate(tmp_path, fact)
    response = _call(tmp_path, "validate_facts", {"document_sha256": SHA256, "fact_ids": [fact_id], "redact_evidence_text": True})

    assert response["result"]["facts"][0]["evidence"] == [{"evidence_id": "block:1", "artifact_scope": "pypdf-all", "document_name": "可信报告.pdf", "physical_page": 1, "locator": "block:block:1", "exact_text": ""}]


def test_harness_bridge_rejects_a_model_supplied_fact_payload(tmp_path: Path) -> None:
    scope = tmp_path / SHA256 / "pypdf-all"
    scope.mkdir(parents=True)
    (scope / "blocks.jsonl").write_text(json.dumps({"evidence_id": "block:1", "physical_page": 1, "exact_text": "可信文本"}) + "\n")
    fact = {
        "fact_id": "fact:1", "field_id": "security_code", "entity_key": "security:2689075", "status": "disclosed", "value": "2689075",
        "evidence": [{"evidence_id": "invented", "artifact_scope": "pypdf-all", "document_name": "sample.pdf", "physical_page": 1, "locator": "row", "exact_text": "伪造文本"}],
    }

    with pytest.raises(subprocess.CalledProcessError):
        _call(tmp_path, "validate_facts", {"document_sha256": SHA256, "facts": [fact]})


def test_harness_bridge_get_page_never_returns_block_text(tmp_path: Path) -> None:
    scope = tmp_path / SHA256 / "pypdf-all"
    scope.mkdir(parents=True)
    (scope / "page-quality.jsonl").write_text(json.dumps({"physical_page": 1, "native_char_count": 5}) + "\n")
    (scope / "blocks.jsonl").write_text(json.dumps({"evidence_id": "block:1", "physical_page": 1, "exact_text": "不可外发全文"}) + "\n")

    response = _call(tmp_path, "get_page", {"document_sha256": SHA256, "scope": "pypdf-all", "physical_page": 1})

    assert response["result"] == {"page": {"physical_page": 1, "native_char_count": 5}, "block_count": 1}
