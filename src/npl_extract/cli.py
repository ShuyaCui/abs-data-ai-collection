from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from npl_extract.intake import inspect_pdf
from npl_extract.contracts import ExtractionFact, ReviewAction
from npl_extract.extract import (
    extract_issuance_announcement_facts,
    extract_issuance_result_ocr_facts,
    extract_prospectus_issue_amount_facts,
    extract_prospectus_market_facts,
    extract_prospectus_actual_financing_entity_facts,
    extract_prospectus_revolving_purchase_fact,
    extract_prospectus_first_interest_payment_facts,
    extract_prospectus_issue_rating_facts,
    extract_rating_report_facts,
    extract_trustee_report_facts,
)
from npl_extract.parsers import parse_native_pdf_isolated, parser_identity
from npl_extract.pipeline import persist_facts, persist_page_artifacts, persist_review_decision, stage_verified_pdf
from npl_extract.review import review_fact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="npl-extract")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect_command = commands.add_parser("inspect", help="validate one local PDF")
    inspect_command.add_argument("pdf", type=Path)
    parse_command = commands.add_parser("parse", help="write native-text evidence artifacts for one local PDF")
    parse_command.add_argument("pdf", type=Path)
    parse_command.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parse_command.add_argument("--native-parser", choices=["pypdf", "docling", "docling-ocr"], default="pypdf")
    parse_command.add_argument("--pages", type=_page_range)
    parse_command.add_argument("--document-name")
    trustee_command = commands.add_parser("extract-trustee", help="extract deterministic trustee-report facts")
    trustee_command.add_argument("pdf", type=Path)
    trustee_command.add_argument("--entity-key", required=True)
    trustee_command.add_argument("--runs-dir", type=Path, default=Path("runs"))
    trustee_command.add_argument("--native-parser", choices=["pypdf", "docling", "docling-ocr"], default="pypdf")
    trustee_command.add_argument("--pages", type=_page_range)
    trustee_command.add_argument("--document-name")
    extract_command = commands.add_parser("extract", help="extract deterministic facts for one supported PDF")
    extract_command.add_argument("pdf", type=Path)
    extract_command.add_argument("--entity-key")
    extract_command.add_argument("--runs-dir", type=Path, default=Path("runs"))
    extract_command.add_argument("--native-parser", choices=["pypdf", "docling", "docling-ocr"], default="pypdf")
    extract_command.add_argument("--pages", type=_page_range)
    extract_command.add_argument("--document-name")
    extract_command.add_argument("--association-facts", type=Path, nargs="+")
    export_command = commands.add_parser("export", help="project persisted facts to a 42-field workbook")
    export_command.add_argument("--template", type=Path, required=True)
    export_command.add_argument("--facts", type=Path, nargs="+", required=True)
    export_command.add_argument("--output", type=Path, required=True)
    review_command = commands.add_parser("review", help="append one immutable human decision for a candidate fact")
    review_command.add_argument("--document-sha256", required=True)
    review_command.add_argument("--facts", type=Path, nargs="+", required=True)
    review_command.add_argument("--fact-id", required=True)
    review_command.add_argument("--action", choices=[action.value for action in ReviewAction], required=True)
    review_command.add_argument("--decision-id", required=True)
    review_command.add_argument("--reviewer-id", required=True)
    review_command.add_argument("--reason-code", required=True)
    review_command.add_argument("--corrected-fact", type=Path)
    review_command.add_argument("--runs-dir", type=Path, default=Path("runs"))
    args = parser.parse_args(argv)
    if args.command == "export":
        from npl_extract.export import export_facts

        try:
            facts = _load_facts(args.facts)
            export_facts(args.template, facts, args.output)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(_json({"error": str(error)}))
            return 2
        print(_json({"output": str(args.output), "fact_count": len(facts)}))
        return 0
    if args.command == "review":
        try:
            candidates = [fact for fact in _load_review_facts(args.document_sha256, args.facts, args.runs_dir) if fact.fact_id == args.fact_id]
            if len(candidates) != 1:
                raise ValueError("review requires exactly one candidate fact ID")
            corrections = _load_review_facts(args.document_sha256, [args.corrected_fact], args.runs_dir) if args.corrected_fact else []
            if len(corrections) > 1:
                raise ValueError("review accepts at most one corrected fact")
            decision = review_fact(
                candidates[0],
                action=ReviewAction(args.action),
                decision_id=args.decision_id,
                reviewer_id=args.reviewer_id,
                reason_code=args.reason_code,
                decided_at=datetime.now(UTC),
                corrected_fact=corrections[0] if corrections else None,
            )
            persisted = persist_review_decision(args.document_sha256, decision, args.runs_dir)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(_json({"error": str(error)}))
            return 2
        print(_json({**persisted.decision.model_dump(mode="json"), "path": str(persisted.path), "reused": persisted.reused}))
        return 0
    if args.command == "extract-trustee" and not args.entity_key.startswith("report:"):
        print(_json([]))
        return 3
    result = inspect_pdf(args.pdf)
    if args.command == "inspect" or not result.accepted:
        print(_json(asdict(result)))
        return 0 if result.accepted else 2
    staged_pdf = stage_verified_pdf(args.pdf, result.document_sha256, args.runs_dir)
    document_name = args.document_name or args.pdf.name
    parser_id = parser_identity(args.native_parser)
    scope = _scope(parser_id, args.pages)
    pages = parse_native_pdf_isolated(staged_pdf, parser=args.native_parser, expected_sha256=result.document_sha256, page_range=args.pages)
    if args.command in {"extract-trustee", "extract"}:
        if args.command == "extract-trustee":
            facts = extract_trustee_report_facts(pages, document_name, args.entity_key, scope)
        elif "簿记建档发行结果公告" in document_name:
            facts = extract_issuance_result_ocr_facts(pages, document_name, scope)
        elif args.entity_key and args.entity_key.startswith("product:") and "发行公告" in document_name:
            facts = extract_issuance_announcement_facts(pages, document_name, args.entity_key, scope)
        elif args.entity_key and args.entity_key.startswith("product:") and "信用评级报告" in document_name:
            facts = extract_rating_report_facts(pages, document_name, args.entity_key, scope)
        elif args.entity_key and args.entity_key.startswith("product:") and "发行说明书" in document_name:
            facts = extract_prospectus_issue_amount_facts(pages, document_name, args.entity_key, scope)
            facts.extend(extract_prospectus_market_facts(pages, document_name, args.entity_key, scope))
            facts.extend(extract_prospectus_revolving_purchase_fact(pages, document_name, args.entity_key, scope))
            facts.extend(extract_prospectus_actual_financing_entity_facts(pages, document_name, args.entity_key, scope))
            if args.association_facts:
                try:
                    association_facts = _load_facts(args.association_facts)
                except (OSError, ValueError) as error:
                    print(_json({"error": str(error)}))
                    return 2
                facts.extend(extract_prospectus_first_interest_payment_facts(pages, document_name, association_facts, scope))
                facts.extend(extract_prospectus_issue_rating_facts(pages, document_name, association_facts, scope))
        else:
            facts = []
        if facts:
            persist_page_artifacts(result.document_sha256, pages, args.runs_dir, scope=scope, parser_identity=parser_id)
            persist_facts(result.document_sha256, facts, args.runs_dir)
            print(_json([fact.model_dump(mode="json") for fact in facts]))
        else:
            print(_json([]))
        return 0 if facts else 3
    artifacts = persist_page_artifacts(result.document_sha256, pages, args.runs_dir, scope=scope, parser_identity=parser_id)
    print(_json({"intake": asdict(result), "run_dir": str(artifacts.run_dir), "reused": artifacts.reused}))
    return 0


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _load_facts(paths: list[Path]) -> list[ExtractionFact]:
    return [
        ExtractionFact.model_validate(json.loads(line))
        for path in paths
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_review_facts(document_sha256: str, paths: list[Path], runs_dir: Path) -> list[ExtractionFact]:
    fact_dir = (runs_dir / document_sha256 / "facts").resolve()
    facts = []
    for path in paths:
        resolved = path.resolve()
        if resolved.parent != fact_dir or resolved.suffix != ".jsonl":
            raise ValueError("review facts must be canonical artifacts for the specified document")
        content = resolved.read_bytes()
        if sha256(content).hexdigest() != resolved.stem:
            raise ValueError("review fact artifact is not content-addressed")
        facts.extend(ExtractionFact.model_validate(json.loads(line)) for line in content.decode("utf-8").splitlines() if line.strip())
    return facts


def _page_range(value: str) -> tuple[int, int]:
    try:
        start, end = (int(item) for item in value.split("-", 1))
    except ValueError as error:
        raise argparse.ArgumentTypeError("pages must be START-END") from error
    if start < 1 or end < start:
        raise argparse.ArgumentTypeError("pages must be positive and ascending")
    return start, end


def _scope(parser_id: str, page_range: tuple[int, int] | None) -> str:
    return f"{parser_id}-pages-{page_range[0]}-{page_range[1]}" if page_range else f"{parser_id}-all"


if __name__ == "__main__":
    raise SystemExit(main())
