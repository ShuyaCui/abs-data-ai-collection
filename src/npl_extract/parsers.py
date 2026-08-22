from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

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
    bbox: list[float] | None


@dataclass(frozen=True)
class PageContent:
    physical_page: int
    native_text: str
    blocks: list[Block] = field(default_factory=list)
    has_complex_table: bool = False


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
