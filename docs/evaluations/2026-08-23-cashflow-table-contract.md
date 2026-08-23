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

## Remaining environment gate

The local host is Apple Silicon (`arm64`), and its Docker daemon is unavailable. Earlier `linux/amd64` emulation reached PP-Structure but OOM-killed table recognition, so no further emulation tuning is valid evidence.

Run this on a native x86 Linux host with Docker and `pdftoppm`:

```bash
cd /path/to/上海国智-demo作业
./docker/build-ppstructure.sh
mkdir -p /tmp/npl-field39-x86
pdftoppm -f 112 -l 113 -r 150 -png \
  'data/臻粹2026年第二期不良资产证券_测试样例2/臻粹2026年第二期不良资产支持证券发行说明书.pdf' \
  /tmp/npl-field39-x86/prospectus
./docker/run-ppstructure-smoke.sh /tmp/npl-field39-x86/prospectus-112.png /tmp/npl-field39-x86/p112 112
./docker/run-ppstructure-smoke.sh /tmp/npl-field39-x86/prospectus-113.png /tmp/npl-field39-x86/p113 113
jq -s '[.[].cells[] | select(.column == 0) | .exact_text | gsub(" "; "") | select(test("^20[0-9]{2}年[0-9]{1,2}月$"))] | length == 37' \
  /tmp/npl-field39-x86/p112/tables.jsonl /tmp/npl-field39-x86/p113/tables.jsonl
```

The final command must return `true`. The output must also contain the three-cell headers and `合计` row on p113 before the frozen MVP acceptance run is allowed.
