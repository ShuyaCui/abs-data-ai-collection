from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from npl_extract.intake import inspect_pdf
from npl_extract.extract import (
    extract_issuance_announcement_facts,
    extract_issuance_result_ocr_facts,
    extract_rating_report_facts,
    extract_trustee_report_facts,
)
from npl_extract.parsers import parse_native_pdf_isolated, parser_identity
from npl_extract.pipeline import persist_facts, persist_page_artifacts, stage_verified_pdf


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
    trustee_command = commands.add_parser("extract-trustee", help="extract deterministic trustee-report facts")
    trustee_command.add_argument("pdf", type=Path)
    trustee_command.add_argument("--entity-key", required=True)
    trustee_command.add_argument("--runs-dir", type=Path, default=Path("runs"))
    trustee_command.add_argument("--native-parser", choices=["pypdf", "docling", "docling-ocr"], default="pypdf")
    trustee_command.add_argument("--pages", type=_page_range)
    extract_command = commands.add_parser("extract", help="extract deterministic facts for one supported PDF")
    extract_command.add_argument("pdf", type=Path)
    extract_command.add_argument("--entity-key")
    extract_command.add_argument("--runs-dir", type=Path, default=Path("runs"))
    extract_command.add_argument("--native-parser", choices=["pypdf", "docling", "docling-ocr"], default="pypdf")
    extract_command.add_argument("--pages", type=_page_range)
    args = parser.parse_args(argv)
    result = inspect_pdf(args.pdf)
    if args.command == "inspect" or not result.accepted:
        print(_json(asdict(result)))
        return 0 if result.accepted else 2
    staged_pdf = stage_verified_pdf(args.pdf, result.document_sha256, args.runs_dir)
    parser_id = parser_identity(args.native_parser)
    scope = _scope(parser_id, args.pages)
    pages = parse_native_pdf_isolated(staged_pdf, parser=args.native_parser, expected_sha256=result.document_sha256, page_range=args.pages)
    if args.command in {"extract-trustee", "extract"}:
        if args.command == "extract-trustee":
            facts = extract_trustee_report_facts(pages, args.pdf.name, args.entity_key, scope)
        elif "簿记建档发行结果公告" in args.pdf.name:
            facts = extract_issuance_result_ocr_facts(pages, args.pdf.name, scope)
        elif args.entity_key and args.entity_key.startswith("product:") and "发行公告" in args.pdf.name:
            facts = extract_issuance_announcement_facts(pages, args.pdf.name, args.entity_key, scope)
        elif args.entity_key and args.entity_key.startswith("product:") and "信用评级报告" in args.pdf.name:
            facts = extract_rating_report_facts(pages, args.pdf.name, args.entity_key, scope)
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
