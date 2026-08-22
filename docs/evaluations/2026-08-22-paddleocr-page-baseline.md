# PaddleOCR page baseline — 2026-08-22

## Scope

Development-only CPU smoke evaluation on page 1 of the scanned ChinaBond rating report. It verifies local package/model installation and text recognition only; it is not a field-accuracy, table-cell, latency, or production-capacity result.

## Frozen input and runtime

- Document SHA-256: `1b3d322806a4ef15eea637c8e2d3e1ffdbe5f92478360f60fa6f8445e5b5371b`.
- Page: 1, rendered locally by macOS Quick Look into a temporary PNG.
- Packages: PaddlePaddle 3.3.1, PaddleOCR 3.7.0, PaddleX 3.7.2.
- Models: `PP-OCRv5_mobile_det` and `PP-OCRv5_mobile_rec`, downloaded locally from the official BOS source into a temporary `PADDLE_PDX_CACHE_HOME`.
- Options: CPU; document orientation, unwarping, and textline orientation disabled.

## Result

- `PaddleOCR.predict()` returned 15 recognized text items.
- PP-StructureV3 completed model initialization with its table models locally cached, but did not yield a structured result on this macOS development host. Do not use this host result to accept or reject the table pipeline.

## Decision

Keep the lightweight PaddleOCR path as an installed local OCR candidate. Validate PP-StructureV3 table/cell evidence in the production-like Linux CPU/GPU container, where model assets are preloaded and their image digest/asset hashes are recorded.
