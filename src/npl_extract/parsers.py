from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PageRoute(str, Enum):
    NATIVE = "native"
    OCR = "ocr"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class Block:
    evidence_id: str
    physical_page: int
    exact_text: str
    bbox: list[float]


@dataclass(frozen=True)
class PageContent:
    physical_page: int
    native_text: str
    blocks: list[Block] = field(default_factory=list)
    has_complex_table: bool = False


def route_page(page: PageContent) -> PageRoute:
    if page.has_complex_table and page.native_text.strip():
        return PageRoute.HYBRID
    return PageRoute.NATIVE if page.native_text.strip() else PageRoute.OCR
