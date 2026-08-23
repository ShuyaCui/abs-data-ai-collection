from __future__ import annotations

import json
import hashlib
import os
import sys
from dataclasses import asdict
from pathlib import Path

from paddleocr import PPStructureV3
from npl_extract.parsers import tables_from_ppstructure_result


def verify_models() -> None:
    root = Path("/opt/paddlex/official_models")
    manifest = root.parent / "MODELS.sha256"
    for line in manifest.read_text().splitlines():
        digest, relative = line.split("  ", 1)
        with (root / relative).open("rb") as model:
            actual = hashlib.file_digest(model, "sha256").hexdigest()
        if actual != digest:
            raise SystemExit(f"model checksum mismatch: {relative}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: ppstructure_smoke.py /input/IMAGE_OR_PDF")
    source = Path(sys.argv[1])
    if source.parent != Path("/input") or not source.is_file():
        raise SystemExit("input must be a single file mounted under /input")
    output = Path("/output")
    if not output.is_dir():
        raise SystemExit("/output must be a writable mounted directory")
    verify_models()
    physical_page = int(os.environ.get("NPL_PPSTRUCTURE_PHYSICAL_PAGE", "1"))
    if physical_page < 1:
        raise SystemExit("NPL_PPSTRUCTURE_PHYSICAL_PAGE must be positive")
    pipeline = PPStructureV3(
        device="cpu",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        use_formula_recognition=False,
        use_chart_recognition=False,
        use_region_detection=False,
    )
    results = pipeline.predict(str(source))
    if not isinstance(results, list):
        results = list(results)
    summary = []
    tables = []
    for index, result in enumerate(results, 1):
        payload = result.json
        (output / f"page-{index:03}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        parsed = payload["res"]
        tables.extend(asdict(table) for table in tables_from_ppstructure_result(payload, physical_page=physical_page + index - 1))
        summary.append(
            {
                "layout_blocks": len(parsed.get("layout_det_res", {}).get("boxes", [])),
                "ocr_items": len(parsed.get("overall_ocr_res", {}).get("rec_texts", [])),
                "table_results": len(parsed.get("table_res_list", [])),
                "table_cells": sum(len(table["cells"]) for table in tables),
            }
        )
    if tables:
        (output / "tables.jsonl").write_text("".join(json.dumps(table, ensure_ascii=False) + "\n" for table in tables), encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
