# Field 39 cash-flow table contract — 2026-08-23

## Real source and expected shape

- Source: `臻粹2026年第二期不良资产支持证券发行说明书.pdf`, SHA-256 `ff3326e013da7376d0ead143c44ea797f662b8c0af6e2f0a85f773d5ed21a679`.
- Native-text reconnaissance locates the table heading and header on p112, continuation header on p113, 37 monthly rows (`2026-01` through `2029-01`) and the disclosed total `24,827.66` 万元 / `100.00%`.
- The 37 amounts sum to `24,827.67` 万元 and ratios sum to `99.99%`. The acceptance tolerance is calculated from the displayed precision: `37 × 0.5 × 10^-2 = 0.185`, not a hard-coded `0.01`.

## Implemented contract

`PPStructureV3` raw `table_res_list` is normalized through its documented `pred_html`, `table_ocr_pred.rec_texts`, and `table_ocr_pred.rec_boxes` fields into parser-owned `table_id`, row, column, exact text and bbox artifacts. A fact is emitted only when:

1. every header/data/total cell has an exact 4-coordinate bbox;
2. each row has period, amount and ratio cells;
3. the disclosed total is present and within the calculated rounding tolerance.

Each monthly row is a `cashflow_row:` fact. A final `total` row retains both disclosed totals and deterministic recomputed totals/tolerances. The Excel export writes a dedicated `现金流归集表` worksheet; all individual header/cell evidence remains in the `证据` worksheet. Harness evidence retrieval and validation resolve table cells without treating them as text blocks.

## Offline proof

- PP-Structure raw-to-cell normalization, table persistence, Field 39 extraction/total validation, Excel output, and Harness retrieve/validate tests pass.
- The artifact pipeline version is `v4`; v3 empty `tables.jsonl` artifacts are deliberately rebuilt rather than reused.
- Real p112–113 native-text extraction returns no Field 39 candidate (exit 3), which is the intended fail-closed result until cell coordinates exist. Native text is not relabelled as table-cell evidence.

## Real native macOS preflight — 2026-08-26

- On the Apple-Silicon host, PP-StructureV3 processed the real rendered p112–113 at 150 DPI with local model cache `runs/paddle-models`; it returned 3 raw table results on p112 and 1 on p113. The contract normalized the cash-flow tables to 51 and 69 coordinate-bearing cells respectively.
- Real extraction emitted 38 facts: monthly `2026-01` through `2029-01` plus `total`. The final row retains disclosed `24,827.66` 万元 / `100.00%`, recomputed `24,827.67` 万元 / `99.99%`, and the calculated `0.185` tolerance.
- The unified original-PDF batch produced `runs/sample/mvp-v0-field39-candidate.{jsonl,xlsx,manifest.json}`. Its independent rerun is byte-identical; the native-x86 Docker preflight is no longer an MVP gate. Native-x86 capacity benchmarking remains a later production concern, not an acceptance blocker.
