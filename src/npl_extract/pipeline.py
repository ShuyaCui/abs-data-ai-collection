from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from npl_extract.parsers import PageContent, route_page


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACT_FILES = ("manifest.json", "page-quality.jsonl", "blocks.jsonl", "tables.jsonl")
_PIPELINE_VERSION = "v2"


@dataclass(frozen=True)
class PersistedArtifacts:
    run_dir: Path
    reused: bool


def persist_page_artifacts(document_sha256: str, pages: list[PageContent], output_root: Path) -> PersistedArtifacts:
    """Persist parser-owned page facts once for a content hash."""
    if not _SHA256.fullmatch(document_sha256):
        raise ValueError("document_sha256 must be a lowercase SHA-256 digest")
    run_dir = output_root / document_sha256
    if _is_complete(run_dir, document_sha256):
        return PersistedArtifacts(run_dir, reused=True)
    run_dir.mkdir(parents=True, exist_ok=True)
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
                "bbox_valid_ratio": (
                    sum(block.bbox is not None and len(block.bbox) == 4 for block in page.blocks) / len(page.blocks)
                    if page.blocks
                    else 0.0
                ),
                "route": route.value,
            }
        )
        blocks.extend(asdict(block) for block in page.blocks)
    _atomic_write(run_dir / "page-quality.jsonl", "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in diagnostics))
    _atomic_write(run_dir / "blocks.jsonl", "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in blocks))
    _atomic_write(run_dir / "tables.jsonl", "")
    _atomic_write(run_dir / "manifest.json", json.dumps({"document_sha256": document_sha256, "pipeline_version": _PIPELINE_VERSION}, ensure_ascii=False))
    return PersistedArtifacts(run_dir, reused=False)


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content)
    temporary.replace(path)


def _is_complete(run_dir: Path, document_sha256: str) -> bool:
    if not run_dir.is_dir() or not all((run_dir / name).is_file() for name in _ARTIFACT_FILES):
        return False
    try:
        manifest = json.loads((run_dir / "manifest.json").read_text())
    except json.JSONDecodeError:
        return False
    return manifest == {"document_sha256": document_sha256, "pipeline_version": _PIPELINE_VERSION}
