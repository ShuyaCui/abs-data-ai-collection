from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from pypdf import PdfReader


class PageRoute(str, Enum):
    NATIVE = "native"
    OCR = "ocr"
    HYBRID = "hybrid"


MIN_NATIVE_CHARS = 8


@dataclass(frozen=True)
class Block:
    evidence_id: str
    physical_page: int
    exact_text: str
    bbox: list[float] | None  # PDF points, [left, top, right, bottom], top-left origin.


@dataclass(frozen=True)
class PageContent:
    physical_page: int
    native_text: str
    blocks: list[Block] = field(default_factory=list)
    has_complex_table: bool = False
    page_width: float | None = None
    page_height: float | None = None


def route_page(page: PageContent) -> PageRoute:
    if page.has_complex_table and page.native_text.strip():
        return PageRoute.HYBRID
    return PageRoute.NATIVE if len(page.native_text.strip()) >= MIN_NATIVE_CHARS else PageRoute.OCR


class PypdfNativeParser:
    """Dependency-light native-text fallback; layout geometry remains unavailable."""

    def parse(self, path: Path) -> list[PageContent]:
        reader = PdfReader(path)
        pages = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            blocks = [
                Block(
                    evidence_id=f"p{page_number:03d}:b{block_number:03d}",
                    physical_page=page_number,
                    exact_text=line,
                    bbox=None,
                )
                for block_number, line in enumerate((line for line in text.splitlines() if line.strip()), start=1)
            ]
            pages.append(PageContent(page_number, text, blocks))
        return pages


class DoclingNativeParser:
    """Local native-text parser with layout coordinates; OCR and table rebuild stay disabled."""

    def parse(self, path: Path) -> list[PageContent]:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as error:
            raise RuntimeError("install npl-extract[parser] to use Docling") from error

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=PdfPipelineOptions(do_ocr=False, do_table_structure=False)
                )
            }
        )
        document = converter.convert(path).document
        per_page: dict[int, list[Block]] = {page_number: [] for page_number in document.pages}
        for item in document.texts:
            for provenance in item.prov:
                if provenance.page_no not in per_page or not item.text.strip():
                    continue
                bbox = provenance.bbox
                page_height = document.pages[provenance.page_no].size.height
                per_page[provenance.page_no].append(
                    Block("", provenance.page_no, item.text, [bbox.l, page_height - bbox.t, bbox.r, page_height - bbox.b])
                )
        pages = []
        for page_number, blocks in sorted(per_page.items()):
            numbered_blocks = [
                Block(f"p{page_number:03d}:b{index:03d}", page_number, block.exact_text, block.bbox)
                for index, block in enumerate(blocks, start=1)
            ]
            size = document.pages[page_number].size
            pages.append(PageContent(page_number, "\n".join(block.exact_text for block in numbered_blocks), numbered_blocks, page_width=size.width, page_height=size.height))
        return pages


def parse_native_pdf_isolated(path: Path, *, parser: str = "pypdf", timeout_seconds: int = 120) -> list[PageContent]:
    """Run the fallback parser with bounded output and a hard wall-clock limit."""
    with tempfile.NamedTemporaryFile(mode="w+b") as output:
        completed = subprocess.run(
            [sys.executable, "-m", "npl_extract.parser_worker", "--parser", parser, str(path)],
            stdout=output,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
        )
        output.seek(0)
        payload = output.read().decode() or "{}"
    response = json.loads(payload)
    if isinstance(response, dict) and "error" in response:
        error = response["error"]
        raise RuntimeError(f"{error['code']}: {error['message']}")
    if completed.returncode:
        raise RuntimeError("PARSER_FAILED: parser worker exited unexpectedly")
    return [
        PageContent(
            physical_page=item["physical_page"],
            native_text=item["native_text"],
            blocks=[Block(**block) for block in item["blocks"]],
            has_complex_table=item["has_complex_table"],
            page_width=item.get("page_width"),
            page_height=item.get("page_height"),
        )
        for item in response
    ]
