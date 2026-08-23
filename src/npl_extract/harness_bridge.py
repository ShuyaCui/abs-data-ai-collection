from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from npl_extract.cli import main as cli_main
from npl_extract.contracts import ExtractionFact


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SCOPE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _runs_root() -> Path:
    return Path(os.environ.get("NPL_RUNS_DIR", "runs")).resolve()


def _run_dir(payload: dict[str, object]) -> Path:
    return _runs_root() / _document_sha256(payload)


def _document_sha256(payload: dict[str, object]) -> str:
    document_sha256 = payload.get("document_sha256")
    if not isinstance(document_sha256, str) or not _SHA256.fullmatch(document_sha256):
        raise ValueError("document_sha256 must be a lowercase SHA-256 digest")
    return document_sha256


def _scope_dir(run_dir: Path, scope: object) -> Path:
    if not isinstance(scope, str) or not _SCOPE.fullmatch(scope):
        raise ValueError("scope must be a parser artifact scope")
    return run_dir / scope


def _jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _document_name(run_dir: Path) -> str:
    source = run_dir / "source.json"
    if not source.is_file():
        return "input.pdf"
    document_name = json.loads(source.read_text(encoding="utf-8")).get("document_name")
    if not isinstance(document_name, str) or not document_name:
        raise ValueError("source document metadata is invalid")
    return document_name


def _externalize_facts(facts: list[dict[str, object]], payload: dict[str, object]) -> list[dict[str, object]]:
    redact = payload.get("redact_evidence_text") is True
    max_text_chars = payload.get("max_text_chars")
    if max_text_chars is not None and (not isinstance(max_text_chars, int) or max_text_chars < 1):
        raise ValueError("max_text_chars must be a positive integer")
    remaining = max_text_chars
    for fact in facts:
        for evidence in fact.get("evidence", []):
            if not isinstance(evidence, dict) or not isinstance(evidence.get("exact_text"), str):
                continue
            if redact:
                evidence["exact_text"] = ""
            elif remaining is not None:
                if len(evidence["exact_text"]) > remaining:
                    evidence["exact_text"] = evidence["exact_text"][:remaining]
                    evidence["truncated"] = True
                remaining -= len(evidence["exact_text"])
    return facts


def retrieve_evidence(payload: dict[str, object]) -> dict[str, object]:
    run_dir = _run_dir(payload)
    scope_dir = _scope_dir(run_dir, payload.get("scope"))
    evidence_id = payload.get("evidence_id")
    if not isinstance(evidence_id, str):
        raise ValueError("evidence_id must be a string")
    max_text_chars = payload.get("max_text_chars")
    if max_text_chars is not None and (not isinstance(max_text_chars, int) or max_text_chars < 1):
        raise ValueError("max_text_chars must be a positive integer")
    for evidence in _jsonl(scope_dir / "blocks.jsonl"):
        if evidence.get("evidence_id") == evidence_id:
            excerpt = dict(evidence)
            if max_text_chars is not None and isinstance(excerpt.get("exact_text"), str) and len(excerpt["exact_text"]) > max_text_chars:
                excerpt["exact_text"] = excerpt["exact_text"][:max_text_chars]
                excerpt["truncated"] = True
            return {"operation": "retrieve_evidence", "status": "ok", "result": {"scope": scope_dir.name, "evidence": excerpt}}
    for table in _jsonl(scope_dir / "tables.jsonl"):
        for cell in table.get("cells", []):
            if isinstance(cell, dict) and cell.get("evidence_id") == evidence_id:
                excerpt = dict(cell)
                if max_text_chars is not None and isinstance(excerpt.get("exact_text"), str) and len(excerpt["exact_text"]) > max_text_chars:
                    excerpt["exact_text"] = excerpt["exact_text"][:max_text_chars]
                    excerpt["truncated"] = True
                return {"operation": "retrieve_evidence", "status": "ok", "result": {"scope": scope_dir.name, "evidence": excerpt}}
    return {"operation": "retrieve_evidence", "status": "not_found", "result": {"evidence_id": evidence_id}}


def get_page(payload: dict[str, object]) -> dict[str, object]:
    scope_dir = _scope_dir(_run_dir(payload), payload.get("scope"))
    physical_page = payload.get("physical_page")
    if not isinstance(physical_page, int) or physical_page < 1:
        raise ValueError("physical_page must be a positive integer")
    page = next((item for item in _jsonl(scope_dir / "page-quality.jsonl") if item.get("physical_page") == physical_page), None)
    if page is None:
        return {"operation": "get_page", "status": "not_found", "result": {"physical_page": physical_page}}
    blocks = [item for item in _jsonl(scope_dir / "blocks.jsonl") if item.get("physical_page") == physical_page]
    return {"operation": "get_page", "status": "ok", "result": {"page": page, "block_count": len(blocks)}}


def get_table(payload: dict[str, object]) -> dict[str, object]:
    scope_dir = _scope_dir(_run_dir(payload), payload.get("scope"))
    table_id = payload.get("table_id")
    if not isinstance(table_id, str):
        raise ValueError("table_id must be a string")
    table = next((item for item in _jsonl(scope_dir / "tables.jsonl") if item.get("table_id") == table_id), None)
    if table is None:
        return {"operation": "get_table", "status": "not_found", "result": {"table_id": table_id}}
    return {"operation": "get_table", "status": "ok", "result": {"table_id": table_id, "physical_page": table.get("physical_page")}}


def extract_field_facts(payload: dict[str, object]) -> dict[str, object]:
    run_dir = _run_dir(payload)
    document_sha256 = _document_sha256(payload)
    entity_key = payload.get("entity_key")
    parser = payload.get("native_parser")
    if not isinstance(entity_key, str) or not isinstance(parser, str):
        raise ValueError("entity_key and native_parser are required")
    staged_pdf = run_dir / "input.pdf"
    if not staged_pdf.is_file():
        raise ValueError("staged PDF is missing")
    if sha256(staged_pdf.read_bytes()).hexdigest() != document_sha256:
        raise ValueError("staged PDF hash mismatch")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = cli_main(["extract", str(staged_pdf), "--document-name", _document_name(run_dir), "--entity-key", entity_key, "--native-parser", parser, "--runs-dir", str(_runs_root())])
    if code not in {0, 3}:
        raise ValueError(output.getvalue().strip() or "extractor failed")
    facts = json.loads(output.getvalue())
    if isinstance(facts, list):
        facts = _externalize_facts([fact for fact in facts if isinstance(fact, dict)], payload)
    return {"operation": "extract_field_facts", "status": "ok", "result": facts}


def validate_facts(payload: dict[str, object]) -> dict[str, object]:
    run_dir = _run_dir(payload)
    fact_ids = payload.get("fact_ids")
    if not isinstance(fact_ids, list) or not fact_ids or not all(isinstance(fact_id, str) for fact_id in fact_ids):
        raise ValueError("fact_ids must be a non-empty string array")
    matches: dict[str, ExtractionFact] = {}
    for path in (run_dir / "facts").glob("*.jsonl"):
        content = path.read_bytes()
        if sha256(content).hexdigest() != path.stem:
            continue
        for line in content.decode("utf-8").splitlines():
            fact = ExtractionFact.model_validate(json.loads(line))
            if fact.fact_id in fact_ids:
                if fact.fact_id in matches:
                    raise ValueError(f"candidate fact {fact.fact_id} is ambiguous")
                matches[fact.fact_id] = fact
    if set(matches) != set(fact_ids):
        raise ValueError("candidate facts must be canonical artifacts for the specified document")
    facts = [matches[fact_id] for fact_id in fact_ids]
    canonical_facts = []
    document_name = _document_name(run_dir)
    for fact in facts:
        canonical_evidence = []
        for evidence in fact.evidence:
            blocks = _jsonl(_scope_dir(run_dir, evidence.artifact_scope) / "blocks.jsonl")
            if any(
                block.get("evidence_id") == evidence.evidence_id
                and block.get("physical_page") == evidence.physical_page
                and block.get("exact_text") == evidence.exact_text
                for block in blocks
            ):
                locator = f"block:{evidence.evidence_id}"
            elif any(
                cell.get("evidence_id") == evidence.evidence_id
                and cell.get("physical_page") == evidence.physical_page
                and cell.get("exact_text") == evidence.exact_text
                for table in _jsonl(_scope_dir(run_dir, evidence.artifact_scope) / "tables.jsonl")
                for cell in table.get("cells", [])
                if isinstance(cell, dict)
            ):
                locator = f"table_cell:{evidence.evidence_id}"
            else:
                raise ValueError(f"evidence {evidence.evidence_id} is not parser-owned")
            canonical_evidence.append(evidence.model_copy(update={"document_name": document_name, "locator": locator}))
        canonical_facts.append(fact.model_copy(update={"evidence": canonical_evidence}))
    return {"operation": "validate_facts", "status": "ok", "result": {"facts": _externalize_facts([fact.model_dump(mode="json") for fact in canonical_facts], payload)}}


def request_review(payload: dict[str, object]) -> dict[str, object]:
    run_dir = _run_dir(payload)
    fact_id = payload.get("fact_id")
    if not isinstance(fact_id, str):
        raise ValueError("fact_id must be a string")
    for path in (run_dir / "facts").glob("*.jsonl"):
        content = path.read_bytes()
        if sha256(content).hexdigest() != path.stem:
            continue
        if any(item.get("fact_id") == fact_id for item in _jsonl(path)):
            return {"operation": "request_review", "status": "review_required", "result": {"candidate_fact_id": fact_id}}
    return {"operation": "request_review", "status": "not_found", "result": {"fact_id": fact_id}}


_OPERATIONS = {
    "retrieve_evidence": retrieve_evidence,
    "get_page": get_page,
    "get_table": get_table,
    "extract_field_facts": extract_field_facts,
    "validate_facts": validate_facts,
    "request_review": request_review,
}


def main(argv: list[str] | None = None) -> int:
    operation = (argv or sys.argv[1:])[0]
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        raise ValueError("worker payload must be an object")
    print(json.dumps(_OPERATIONS[operation](payload), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
