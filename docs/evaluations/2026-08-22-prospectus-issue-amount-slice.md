# Prospectus issue-amount slice — 2026-08-22

Command: `npl-extract extract <发行说明书> --entity-key product:臻粹2026-2 --pages 2-2` using the local `pypdf` parser. No model call or document egress occurred.

| Field | Value | Evidence |
|---|---:|---|
| `issue_amount_senior` | `1.32` CNY_100M | p2 “证券名称 / 发行金额（万元）” header; 优先档 row `13,200.00` |
| `issue_amount_mezzanine` | `not_applicable` (no numeric value) | p2 complete two-row table: 优先档 and 次级档 only |
| `issue_amount_subordinated` | `0.5` CNY_100M | p2 same header; 次级档 row `5,000.00` |

The extractor accepts one native-text prospectus table header through its `总计`/`合计` row and one row per recognized level. Duplicate headers or duplicate level rows reject the complete result. Because the complete sample table contains only the senior and subordinated rows, it emits `issue_amount_mezzanine=not_applicable` with no numeric value; it never infers a zero amount.
