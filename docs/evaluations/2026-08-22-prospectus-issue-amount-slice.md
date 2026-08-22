# Prospectus issue-amount slice — 2026-08-22

Command: `npl-extract extract <发行说明书> --entity-key product:臻粹2026-2 --pages 2-2` using the local `pypdf` parser. No model call or document egress occurred.

| Field | Value | Evidence |
|---|---:|---|
| `issue_amount_senior` | `1.32` CNY_100M | p2 “证券名称 / 发行金额（万元）” header; 优先档 row `13,200.00` |
| `issue_amount_subordinated` | `0.5` CNY_100M | p2 same header; 次级档 row `5,000.00` |

The extractor accepts one native-text prospectus table header and one row per recognized level within the next five blocks. Duplicate headers or duplicate level rows reject the complete result. `issue_amount_mezzanine` remains unfilled because this sample directly discloses no 次优档/次优级 row; the workflow does not infer a zero amount.
