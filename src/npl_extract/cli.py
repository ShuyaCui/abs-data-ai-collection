from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from npl_extract.intake import inspect_pdf
from npl_extract.extract import extract_trustee_report_facts
from npl_extract.parsers import parse_native_pdf_isolated
from npl_extract.pipeline import persist_facts, persist_page_artifacts, stage_verified_pdf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="npl-extract")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect_command = commands.add_parser("inspect", help="validate one local PDF")
    inspect_command.add_argument("pdf", type=Path)
    parse_command = commands.add_parser("parse", help="write native-text evidence artifacts for one local PDF")
    parse_command.add_argument("pdf", type=Path)
    parse_command.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parse_command.add_argument("--native-parser", choices=["pypdf", "docling"], default="pypdf")
    trustee_command = commands.add_parser("extract-trustee", help="extract deterministic trustee-report facts")
    trustee_command.add_argument("pdf", type=Path)
    trustee_command.add_argument("--entity-key", required=True)
    trustee_command.add_argument("--runs-dir", type=Path, default=Path("runs"))
    trustee_command.add_argument("--native-parser", choices=["pypdf", "docling"], default="pypdf")
    args = parser.parse_args(argv)
    result = inspect_pdf(args.pdf)
    if args.command == "inspect" or not result.accepted:
        print(_json(asdict(result)))
        return 0 if result.accepted else 2
    staged_pdf = stage_verified_pdf(args.pdf, result.document_sha256, args.runs_dir)
    pages = parse_native_pdf_isolated(staged_pdf, parser=args.native_parser)
    if args.command == "extract-trustee":
        facts = extract_trustee_report_facts(pages, args.pdf.name, args.entity_key)
        if facts:
            persist_page_artifacts(result.document_sha256, pages, args.runs_dir)
            persist_facts(result.document_sha256, facts, args.runs_dir)
            print(_json([fact.model_dump(mode="json") for fact in facts]))
        else:
            print(_json([]))
        return 0 if facts else 3
    artifacts = persist_page_artifacts(result.document_sha256, pages, args.runs_dir)
    print(_json({"intake": asdict(result), "run_dir": str(artifacts.run_dir), "reused": artifacts.reused}))
    return 0


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


if __name__ == "__main__":
    raise SystemExit(main())
