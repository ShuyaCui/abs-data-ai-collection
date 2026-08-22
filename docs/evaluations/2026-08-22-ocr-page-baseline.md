# OCR page baseline — 2026-08-22

## Scope

Development-only smoke evaluation of the first page of the sample's scanned ChinaBond rating report. This is not a field-accuracy evaluation and does not establish production capacity.

## Frozen input

- Document: `臻粹2026年第二期不良资产支持证券信用评级报告及跟踪评级安排(中债资信).pdf`
- SHA-256: `1b3d322806a4ef15eea637c8e2d3e1ffdbe5f92478360f60fa6f8445e5b5371b`
- Page range: 1–1
- Engine: local Docling 2.121.0 with RapidOCR; table reconstruction disabled.
- Command: `npl-extract parse <pdf> --native-parser docling-ocr --pages 1-1`
- Artifact path relative to `--runs-dir`: `1b3d322806a4ef15eea637c8e2d3e1ffdbe5f92478360f60fa6f8445e5b5371b/docling-2-121-0-rapidocr-3-9-2-ocr-no-table-pages-1-1/`.

## Result

- The command completed successfully on the local development host.
- `docling-2-121-0-rapidocr-3-9-2-ocr-pages-1-1/blocks.jsonl`: 11 blocks, all with bounding boxes.
- Page diagnostic has `ocr_requested: true`; this records the selected worker configuration, not the source of every block. Its `route` is evaluated from returned text and is labelled `route_basis: returned_text`, so it is not an OCR-rate metric.
- `manifest.json` records pipeline `v3` and parser identity `docling-2-121-0-rapidocr-3-9-2-ocr-no-table`.
- The artifact scope includes both engine and page range, so it cannot be reused as pypdf, native Docling, or whole-document output.

## Decision

Keep RapidOCR only as a local integration baseline. Do not claim its one-page timing or text quality as a production result. The production OCR/table candidate remains PaddleOCR PP-StructureV3 and needs its own benchmark plus cell-evidence acceptance test.
