from __future__ import annotations

import argparse
import json
import re
import tempfile
from contextlib import contextmanager
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
    extract_prospectus_initial_face_value_facts,
    extract_prospectus_market_facts,
    extract_prospectus_actual_financing_entity_facts,
    extract_prospectus_revolving_purchase_fact,
    extract_prospectus_first_interest_payment_facts,
    extract_prospectus_issue_rating_facts,
    extract_cashflow_collection_table_facts,
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
    folder_command = commands.add_parser("extract-folder", help="extract supported PDFs in one local folder")
    folder_command.add_argument("input_dir", type=Path)
    folder_command.add_argument("--product-key", required=True)
    folder_command.add_argument("--product-name", required=True, help="canonical product display name used to bind source documents")
    folder_command.add_argument("--template", type=Path, required=True)
    folder_command.add_argument("--output", type=Path, required=True)
    folder_command.add_argument("--runs-dir", type=Path, default=Path("runs"))
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
    if args.command == "extract-folder":
        return _extract_folder(args)
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
            facts.extend(extract_cashflow_collection_table_facts(pages, document_name, args.entity_key, scope))
            if args.association_facts:
                try:
                    association_facts = _load_facts(args.association_facts)
                except (OSError, ValueError) as error:
                    print(_json({"error": str(error)}))
                    return 2
                facts.extend(extract_prospectus_first_interest_payment_facts(pages, document_name, association_facts, scope))
                facts.extend(extract_prospectus_issue_rating_facts(pages, document_name, association_facts, scope))
                facts.extend(extract_prospectus_initial_face_value_facts(pages, document_name, association_facts, scope))
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


def _extract_folder(args: argparse.Namespace) -> int:
    """Run the supported deterministic routes in one folder and write an auditable batch manifest."""
    from npl_extract.export import export_facts

    input_dir = args.input_dir.resolve()
    output_path = args.output.resolve()
    if not input_dir.is_dir() or not args.product_key.startswith("product:") or not args.product_name.strip():
        print(_json({"error": "extract-folder requires an existing directory, product: key, and product name"}))
        return 2
    if output_path.suffix.lower() != ".xlsx" or _is_within(output_path, input_dir) or args.template.resolve() == output_path:
        print(_json({"error": "extract-folder output must be an .xlsx outside the input directory"}))
        return 2
    try:
        with _exclusive_output_lock(output_path):
            return _extract_folder_locked(args, input_dir, output_path)
    except BlockingIOError:
        print(_json({"error": "extract-folder output is already in use"}))
        return 2


def _extract_folder_locked(args: argparse.Namespace, input_dir: Path, output_path: Path) -> int:
    documents = []
    for path in sorted(input_dir.glob("*.pdf")):
        role = _folder_role(path.name)
        document = {"document_name": path.name, "source_sha256": sha256(path.read_bytes()).hexdigest()}
        if role is None:
            documents.append({**document, "status": "unsupported"})
            continue
        result = inspect_pdf(path, input_root=input_dir)
        if not result.accepted:
            documents.append({**document, "role": role, "status": "rejected", "failure_code": result.failure_code.value})
            continue
        documents.append(
            {
                **document,
                "role": role,
                "status": "queued",
                "page_count": result.page_count,
                "product_identity": _document_product_identity(path.name, role),
            }
        )
    identities = {
        document["product_identity"]
        for document in documents
        if document["status"] == "queued" and document.get("product_identity")
    }
    if identities != {_canonical_product_identity(args.product_name)}:
        for document in documents:
            if document["status"] == "queued":
                document["status"] = "ambiguous"
                document["error_code"] = "PRODUCT_IDENTITY_MISMATCH"
    for role in ("issuance_announcement", "issuance_result", "prospectus"):
        duplicates = [document for document in documents if document.get("role") == role and document["status"] == "queued"]
        if len(duplicates) > 1:
            for document in duplicates:
                document["status"] = "ambiguous"
                document["error_code"] = "DUPLICATE_DOCUMENT_ROLE"
    trustees = [document for document in documents if document.get("role") == "trustee" and document["status"] == "queued"]
    if trustees:
        periods = {document["document_name"]: _trustee_period(Path(document["document_name"])) for document in trustees}
        latest_period = max(periods.values())
        latest = [name for name, period in periods.items() if period == latest_period]
        if latest_period < 1 or len(latest) != 1:
            for document in trustees:
                document["status"] = "ambiguous"
                document["error_code"] = "TRUSTEE_PERIOD_AMBIGUOUS"
        else:
            for document in trustees:
                if document["document_name"] != latest[0]:
                    document["status"] = "superseded"
    facts: list[ExtractionFact] = []
    associations: list[ExtractionFact] = []
    for role in ("issuance_announcement", "issuance_result", "prospectus", "rating_report", "trustee"):
        queued = [document for document in documents if document.get("role") == role and document["status"] == "queued"]
        if len(queued) != 1:
            continue
        document = queued[0]
        path = input_dir / document["document_name"]
        parser = "docling-ocr" if role == "issuance_result" else "pypdf"
        try:
            staged = stage_verified_pdf(path, document["source_sha256"], args.runs_dir)
            parser_id = parser_identity(parser)
            entity_key = f"report:{args.product_key.removeprefix('product:')}" if role == "trustee" else args.product_key
            extracted: list[ExtractionFact] = []
            ranges = {
                "issuance_announcement": [((1, 2), extract_issuance_announcement_facts)],
                "issuance_result": [((1, 2), extract_issuance_result_ocr_facts)],
                "rating_report": [((4, 4), extract_rating_report_facts)],
                "trustee": [((1, 7), extract_trustee_report_facts)],
                "prospectus": [
                    ((2, 3), None), ((16, 16), extract_prospectus_actual_financing_entity_facts),
                    ((90, 90), extract_prospectus_revolving_purchase_fact), ((120, 121), extract_prospectus_initial_face_value_facts),
                    ((112, 113), extract_cashflow_collection_table_facts),
                ],
            }[role]
            document["parser"] = parser_id
            document["artifact_scopes"] = []
            for page_range, extractor in ranges:
                scope = _scope(parser_id, page_range)
                pages = parse_native_pdf_isolated(staged, parser=parser, expected_sha256=document["source_sha256"], page_range=page_range)
                if role == "prospectus" and page_range == (2, 3):
                    slice_facts = extract_prospectus_issue_amount_facts(pages, path.name, entity_key, scope)
                    slice_facts.extend(extract_prospectus_market_facts(pages, path.name, entity_key, scope))
                    slice_facts.extend(extract_prospectus_first_interest_payment_facts(pages, path.name, associations, scope))
                    slice_facts.extend(extract_prospectus_issue_rating_facts(pages, path.name, associations, scope))
                elif role == "issuance_result":
                    slice_facts = extractor(pages, path.name, scope)
                    associations = slice_facts
                elif role == "trustee":
                    slice_facts = extractor(pages, path.name, entity_key, scope)
                elif role == "prospectus" and extractor is extract_prospectus_initial_face_value_facts:
                    slice_facts = extractor(pages, path.name, associations, scope)
                else:
                    slice_facts = extractor(pages, path.name, entity_key, scope)
                artifacts = persist_page_artifacts(document["source_sha256"], pages, args.runs_dir, scope=scope, parser_identity=parser_id)
                document["artifact_scopes"].append(str(artifacts.run_dir))
                extracted.extend(slice_facts)
            if extracted:
                persisted = persist_facts(document["source_sha256"], extracted, args.runs_dir)
                document["facts_artifact"] = str(persisted.path)
                facts.extend(extracted)
                document["status"] = "processed"
            else:
                document["status"] = "no_facts"
        except (OSError, RuntimeError, ValueError) as error:
            document["status"] = "failed"
            document["error_code"] = _error_code(error)
    issue_amounts = [fact for fact in facts if fact.field_id == "tranche_issue_amount"]
    balances = [fact for fact in facts if fact.field_id == "tranche_current_balance"]
    initial_faces = [fact for fact in facts if fact.field_id == "tranche_initial_face_value"]
    from npl_extract.extract import derive_unit_remaining_face_values

    derived = derive_unit_remaining_face_values(issue_amounts, balances, initial_faces)
    batch_sha256 = sha256(_json({"product_key": args.product_key, "source_sha256": sorted(document["source_sha256"] for document in documents)}).encode()).hexdigest()
    derived_artifact = persist_facts(batch_sha256, derived, args.runs_dir) if derived else None
    facts.extend(derived)
    facts_path = output_path.with_suffix(".jsonl")
    manifest_path = output_path.with_suffix(".manifest.json")
    manifest = {
        "input_dir": str(input_dir), "product_key": args.product_key, "product_name": args.product_name,
        "batch_sha256": batch_sha256, "generated_at": datetime.now(UTC).isoformat(), "documents": documents,
        "derived_facts_artifact": str(derived_artifact.path) if derived_artifact else None, "fact_count": len(facts),
    }
    _publish_batch_outputs(args.template, facts, output_path, facts_path, manifest_path, manifest)
    print(_json({"output": str(output_path), "facts": str(facts_path), "manifest": str(manifest_path), "fact_count": len(facts)}))
    return 0


def _folder_role(document_name: str) -> str | None:
    if "簿记建档发行结果公告" in document_name:
        return "issuance_result"
    if "发行公告" in document_name:
        return "issuance_announcement"
    if "发行说明书" in document_name:
        return "prospectus"
    if "信用评级报告" in document_name and "中诚信国际" in document_name:
        return "rating_report"
    if "受托机构报告" in document_name:
        return "trustee"
    return None


def _trustee_period(path: Path) -> int:
    match = re.search(r"总第(\d+)期", path.name)
    return int(match.group(1)) if match else -1


def _document_product_identity(document_name: str, role: str) -> str:
    stem = Path(document_name).stem
    suffixes = {
        "issuance_announcement": "发行公告",
        "issuance_result": "簿记建档发行结果公告",
        "prospectus": "发行说明书",
    }
    if role in suffixes:
        product = stem.removesuffix(suffixes[role])
    elif role == "rating_report":
        product = stem.split("信用评级报告", 1)[0]
    else:
        product = stem.split("受托机构报告", 1)[0]
    return _canonical_product_identity(product)


def _canonical_product_identity(value: str) -> str:
    value = re.sub(r"\s+", "", value)
    return value.replace("不良资产支持证券", "不良资产").replace("不良资产证券化信托", "不良资产")


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _error_code(error: Exception) -> str:
    match = re.match(r"([A-Z][A-Z0-9_]+):", str(error))
    return match.group(1) if match else error.__class__.__name__.upper()


@contextmanager
def _exclusive_output_lock(output_path: Path):
    try:
        import fcntl
    except ImportError as error:
        raise RuntimeError("PARSER_PLATFORM_UNSUPPORTED: POSIX file locking is required") from error
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.with_suffix(f"{output_path.suffix}.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _publish_batch_outputs(
    template: Path, facts: list[ExtractionFact], output_path: Path, facts_path: Path, manifest_path: Path, manifest: dict[str, object]
) -> None:
    from npl_extract.export import export_facts

    with tempfile.TemporaryDirectory(dir=output_path.parent, prefix=f".{output_path.stem}.") as temporary:
        root = Path(temporary)
        workbook = root / output_path.name
        output_facts = root / facts_path.name
        output_manifest = root / manifest_path.name
        export_facts(template, facts, workbook)
        output_facts.write_text("".join(_json(fact.model_dump(mode="json")) + "\n" for fact in facts), encoding="utf-8")
        output_manifest.write_text(_json(manifest), encoding="utf-8")
        workbook.replace(output_path)
        output_facts.replace(facts_path)
        output_manifest.replace(manifest_path)


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
