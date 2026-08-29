from __future__ import annotations

import sys
from types import SimpleNamespace

from npl_extract.parsers import PPStructureTableParser


def test_ppstructure_empty_prediction_emits_no_table_content(monkeypatch, tmp_path) -> None:
    class Document:
        def __init__(self, path: str) -> None:
            self.path = path

        def __len__(self) -> int:
            return 112

        def __getitem__(self, index: int):
            return SimpleNamespace(render=lambda scale: SimpleNamespace(to_pil=lambda: SimpleNamespace(save=lambda path: None)))

    class Pipeline:
        def __init__(self, **kwargs) -> None:
            pass

        def predict(self, image_path: str):
            return iter(())

    monkeypatch.setitem(sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=Document))
    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PPStructureV3=Pipeline))

    pages = PPStructureTableParser().parse(tmp_path / "prospectus.pdf", (112, 112))

    assert len(pages) == 1
    assert pages[0].physical_page == 112
    assert pages[0].tables == []
