from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from npl_extract.parsers import PageContent, route_page


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PersistedArtifacts:
    run_dir: Path
    reused: bool


def persist_page_artifacts(document_sha256: str, pages: list[PageContent], output_root: Path) -> PersistedArtifacts:
    """Persist parser-owned page facts once for a content hash."""
    if not _SHA256.fullmatch(document_sha256):
        raise ValueError("document_sha256 must be a lowercase SHA-256 digest")
    run_dir = output_root / document_sha256
    manifest = run_dir / "manifest.json"
    if manifest.exists():
        return PersistedArtifacts(run_dir, reused=True)
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest.write_text(json.dumps({"document_sha256": document_sha256, "pipeline_version": "v1"}, ensure_ascii=False))
    diagnostics = []
    blocks = []
    for page in pages:
        route = route_page(page)
        native = page.native_text
        diagnostics.append(
            {
                "physical_page": page.physical_page,
                "native_char_count": len(native),
                "bad_unicode_ratio": native.count("\ufffd") / max(len(native), 1),
                "bbox_valid_ratio": 1.0 if all(len(block.bbox) == 4 for block in page.blocks) else 0.0,
                "route": route.value,
            }
        )
        blocks.extend(asdict(block) for block in page.blocks)
    (run_dir / "page-quality.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in diagnostics))
    (run_dir / "blocks.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in blocks))
    return PersistedArtifacts(run_dir, reused=False)
