from __future__ import annotations

import json
import re
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from npl_extract.contracts import ExtractionFact
from npl_extract.parsers import PageContent, route_page


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACT_FILES = ("manifest.json", "page-quality.jsonl", "blocks.jsonl", "tables.jsonl")
_PIPELINE_VERSION = "v3"


@dataclass(frozen=True)
class PersistedArtifacts:
    run_dir: Path
    reused: bool


@dataclass(frozen=True)
class PersistedFacts:
    path: Path
    reused: bool


def persist_page_artifacts(
    document_sha256: str, pages: list[PageContent], output_root: Path, *, scope: str = "pypdf-all", parser_identity: str = "pypdf-unknown"
) -> PersistedArtifacts:
    """Persist parser-owned page facts once for a content hash."""
    if not _SHA256.fullmatch(document_sha256):
        raise ValueError("document_sha256 must be a lowercase SHA-256 digest")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", scope):
        raise ValueError("scope must contain only lowercase parser and page-range segments")
    run_dir = output_root / document_sha256 / scope
    with _document_lock(output_root, document_sha256):
        if _is_complete(run_dir, document_sha256, scope, parser_identity):
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
                    "bbox_coordinate_system": "pdf_points_top_left" if page.page_width is not None else None,
                    "page_width": page.page_width,
                    "page_height": page.page_height,
                    "ocr_requested": page.ocr_requested,
                    "route_basis": "returned_text",
                    "route": route.value,
                }
            )
            blocks.extend(asdict(block) for block in page.blocks)
        _atomic_write(run_dir / "page-quality.jsonl", "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in diagnostics))
        _atomic_write(run_dir / "blocks.jsonl", "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in blocks))
        _atomic_write(run_dir / "tables.jsonl", "")
        _atomic_write(run_dir / "manifest.json", json.dumps({"document_sha256": document_sha256, "pipeline_version": _PIPELINE_VERSION, "scope": scope, "parser_identity": parser_identity}, ensure_ascii=False))
        return PersistedArtifacts(run_dir, reused=False)


def _atomic_write(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def persist_facts(document_sha256: str, facts: list[ExtractionFact], output_root: Path) -> PersistedFacts:
    """Persist an immutable, content-addressed candidate fact set."""
    if not _SHA256.fullmatch(document_sha256):
        raise ValueError("document_sha256 must be a lowercase SHA-256 digest")
    content = "".join(json.dumps(fact.model_dump(mode="json"), ensure_ascii=False) + "\n" for fact in facts)
    run_dir = output_root / document_sha256
    path = run_dir / "facts" / f"{sha256(content.encode()).hexdigest()}.jsonl"
    with _document_lock(output_root, document_sha256):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            return PersistedFacts(path, reused=True)
        _atomic_write(path, content)
        return PersistedFacts(path, reused=False)


def stage_verified_pdf(path: Path, document_sha256: str, output_root: Path) -> Path:
    """Copy the verified bytes once, then parse only the content-addressed copy."""
    content = path.read_bytes()
    if sha256(content).hexdigest() != document_sha256:
        raise ValueError("PDF changed after intake")
    staged = output_root / document_sha256 / "input.pdf"
    with _document_lock(output_root, document_sha256):
        staged.parent.mkdir(parents=True, exist_ok=True)
        if staged.is_file():
            if sha256(staged.read_bytes()).hexdigest() == document_sha256:
                return staged
            raise ValueError("staged PDF hash mismatch")
        _atomic_write_bytes(staged, content)
        return staged


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


@contextmanager
def _document_lock(output_root: Path, document_sha256: str):
    try:
        import fcntl
    except ImportError as error:
        raise RuntimeError("PARSER_PLATFORM_UNSUPPORTED: POSIX file locking is required") from error

    output_root.mkdir(parents=True, exist_ok=True)
    with (output_root / f".{document_sha256}.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _is_complete(run_dir: Path, document_sha256: str, scope: str, parser_identity: str) -> bool:
    if not run_dir.is_dir() or not all((run_dir / name).is_file() for name in _ARTIFACT_FILES):
        return False
    try:
        manifest = json.loads((run_dir / "manifest.json").read_text())
    except json.JSONDecodeError:
        return False
    return manifest == {"document_sha256": document_sha256, "pipeline_version": _PIPELINE_VERSION, "scope": scope, "parser_identity": parser_identity}
