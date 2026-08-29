from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from contextlib import redirect_stdout
from html.parser import HTMLParser
from importlib.metadata import PackageNotFoundError, version
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
class TableCell:
    evidence_id: str
    physical_page: int
    table_id: str
    row: int
    column: int
    exact_text: str
    bbox: list[float] | None  # Parser-owned coordinates, [left, top, right, bottom].


@dataclass(frozen=True)
class Table:
    table_id: str
    physical_page: int
    cells: list[TableCell]


@dataclass(frozen=True)
class PageContent:
    physical_page: int
    native_text: str
    blocks: list[Block] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    has_complex_table: bool = False
    page_width: float | None = None
    page_height: float | None = None
    ocr_requested: bool = False


class _TableGrid(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def tables_from_ppstructure_result(payload: dict[str, object], *, physical_page: int) -> list[Table]:
    """Normalize PP-StructureV3 table OCR output to parser-owned cells."""
    result = payload.get("res", payload)
    if not isinstance(result, dict):
        return []
    raw_tables = result.get("table_res_list")
    if not isinstance(raw_tables, list):
        return []
    tables = []
    for index, raw_table in enumerate(raw_tables, start=1):
        if not isinstance(raw_table, dict):
            continue
        html = raw_table.get("pred_html")
        table_ocr = raw_table.get("table_ocr_pred")
        if not isinstance(html, str) or not isinstance(table_ocr, dict):
            continue
        grid = _TableGrid()
        grid.feed(html)
        positions = [(row, column) for row, cells in enumerate(grid.rows) for column in range(len(cells))]
        texts = table_ocr.get("rec_texts")
        boxes = table_ocr.get("rec_boxes")
        if not isinstance(texts, list) or not isinstance(boxes, list) or len(positions) != len(texts) or len(texts) != len(boxes):
            continue
        table_id = f"p{physical_page:03d}:t{index:03d}"
        cells = []
        for (row, column), text, bbox in zip(positions, texts, boxes, strict=True):
            if not isinstance(text, str) or not isinstance(bbox, list) or len(bbox) != 4:
                cells = []
                break
            cells.append(TableCell(f"{table_id}:r{row:03d}:c{column:03d}", physical_page, table_id, row, column, text, bbox))
        if cells:
            tables.append(Table(table_id, physical_page, cells))
    return tables


def route_page(page: PageContent) -> PageRoute:
    if (page.has_complex_table or page.tables) and page.native_text.strip():
        return PageRoute.HYBRID
    return PageRoute.NATIVE if len(page.native_text.strip()) >= MIN_NATIVE_CHARS else PageRoute.OCR


class PypdfNativeParser:
    """Dependency-light native-text fallback; layout geometry remains unavailable."""

    def parse(self, path: Path, page_range: tuple[int, int] | None = None) -> list[PageContent]:
        reader = PdfReader(path)
        pages = []
        start, end = page_range or (1, len(reader.pages))
        for page_number in range(start, min(end, len(reader.pages)) + 1):
            page = reader.pages[page_number - 1]
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
    """Local Docling parser with layout coordinates and explicit OCR control."""

    def __init__(self, *, ocr: bool = False) -> None:
        self.ocr = ocr

    def parse(self, path: Path, page_range: tuple[int, int] | None = None) -> list[PageContent]:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as error:
            raise RuntimeError("install npl-extract[parser] to use Docling") from error

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=PdfPipelineOptions(do_ocr=self.ocr, do_table_structure=False)
                )
            }
        )
        document = converter.convert(path, page_range=page_range or (1, sys.maxsize)).document
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
            pages.append(PageContent(page_number, "\n".join(block.exact_text for block in numbered_blocks), numbered_blocks, page_width=size.width, page_height=size.height, ocr_requested=self.ocr))
        return pages


class PPStructureTableParser:
    """Parse only requested PDF pages into PP-Structure table cells."""

    def parse(self, path: Path, page_range: tuple[int, int] | None = None) -> list[PageContent]:
        try:
            import pypdfium2
        except ImportError as error:
            raise RuntimeError("install npl-extract[ocr] to use PP-Structure") from error

        start, end = page_range or (1, len(PdfReader(path).pages))
        document = pypdfium2.PdfDocument(str(path))
        last_page = min(end, len(document))
        if start > last_page:
            return []
        try:
            from paddleocr import PPStructureV3
        except ImportError as error:
            raise RuntimeError("install npl-extract[ocr] to use PP-Structure") from error
        with redirect_stdout(sys.stderr), tempfile.TemporaryDirectory() as image_dir:
            pipeline = PPStructureV3(
                device="cpu",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                use_formula_recognition=False,
                use_chart_recognition=False,
                use_region_detection=False,
            )
            pages = []
            for physical_page in range(start, last_page + 1):
                image_path = Path(image_dir) / f"page-{physical_page}.png"
                document[physical_page - 1].render(scale=150 / 72).to_pil().save(image_path)
                prediction = next(iter(pipeline.predict(str(image_path))), None)
                tables = tables_from_ppstructure_result(prediction.json, physical_page=physical_page) if prediction else []
                pages.append(PageContent(physical_page, "", tables=tables, has_complex_table=bool(tables), ocr_requested=True))
        return pages


def parse_native_pdf_isolated(
    path: Path, *, parser: str = "pypdf", expected_sha256: str | None = None, page_range: tuple[int, int] | None = None, timeout_seconds: int = 120
) -> list[PageContent]:
    """Run the fallback parser with bounded output and a hard wall-clock limit."""
    with tempfile.NamedTemporaryFile(mode="w+b") as output:
        command = [sys.executable, "-m", "npl_extract.parser_worker", "--parser", parser]
        if expected_sha256:
            command.extend(["--expected-sha256", expected_sha256])
        if page_range:
            command.extend(["--page-start", str(page_range[0]), "--page-end", str(page_range[1])])
        command.append(str(path))
        try:
            completed = subprocess.run(command, stdout=output, stderr=subprocess.DEVNULL, timeout=timeout_seconds)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("PARSER_TIMEOUT: parser worker exceeded its time limit") from error
        output.seek(0)
        payload = output.read().decode() or "{}"
    if completed.returncode and not payload.startswith("{"):
        raise RuntimeError("PARSER_FAILED: parser worker exited unexpectedly")
    try:
        response = json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError("PARSER_OUTPUT_INVALID: parser worker returned invalid JSON") from error
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
            tables=[Table(table_id=table["table_id"], physical_page=table["physical_page"], cells=[TableCell(**cell) for cell in table["cells"]]) for table in item.get("tables", [])],
            has_complex_table=item["has_complex_table"],
            page_width=item.get("page_width"),
            page_height=item.get("page_height"),
            ocr_requested=item.get("ocr_requested", False),
        )
        for item in response
    ]


def parser_identity(parser: str) -> str:
    try:
        if parser == "pypdf":
            return f"pypdf-{version('pypdf').replace('.', '-')}"
        if parser == "ppstructure":
            return f"ppstructure-v3-paddleocr-{version('paddleocr').replace('.', '-')}"
        identity = f"docling-{version('docling').replace('.', '-')}"
        if parser == "docling-ocr":
            identity += f"-rapidocr-{version('rapidocr').replace('.', '-')}"
        return identity + ("-ocr-no-table" if parser == "docling-ocr" else "-native-no-table")
    except PackageNotFoundError:
        return f"{parser}-missing"
