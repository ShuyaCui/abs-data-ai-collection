# Page-routing sample evaluation

- Date: 2026-08-22
- Pipeline version: `v2`
- Scope: routing only; not an extraction-accuracy or evidence-geometry claim.
- Inputs remained local under `data/` and are Git-ignored.

| Document role | Pages | Expected native | Expected OCR | Observed native | Observed OCR | Result |
|---|---:|---:|---:|---:|---:|---|
| 发行说明书 | 708 | 707 | 1 | 707 | 1 | pass |
| 2026 年第 4 期受托机构报告 | 13 | 13 | 0 | 13 | 0 | pass |
| 中债资信评级报告 | 30 | 0 | 30 | 0 | 30 | pass |
| Total | 751 | 720 | 31 | 720 | 31 | 100% route agreement |

The one prospectus page with fewer than eight native characters is correctly routed to OCR after the `v2` gate change. The `PypdfNativeParser` produces page/line evidence only and reports no bounding boxes; therefore it is suitable for local routing and candidate retrieval, but cannot by itself satisfy final table-cell/paragraph geometry evidence requirements. The next parser step is an opt-in Docling adapter; scan-routed pages then require PaddleOCR.

## Deterministic trustee-report slice

| Field | Expected | Observed | Evidence | Value result |
|---|---|---|---|---|
| 最新报告日期 | 2026-08-17 | 2026-08-17 | 第 4 期受托报告 p1，封面/报告日期 | pass |
| NPL-受托已回收（亿） | 0.6040795674 | 0.6040795674 | 第 4 期受托报告 p7，四、资产池表现情况/（三）资金池现金流流入/两处置行 | pass |

Both facts remain **provisional**: their page and exact text are correct, but pypdf does not provide table-cell bounding boxes. A Docling/Paddle evidence implementation is required before the review policy may confirm them.
