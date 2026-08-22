# Rating report pool-balance slice — 2026-08-22

## Scope

Native-text rating-report sample: `臻粹2026年第二期不良资产支持证券信用评级报告及跟踪评级安排(中诚信国际).pdf`.

| Field | Expected | Extracted | Evidence | Result |
|---|---:|---:|---|---|
| `initial_pool_outstanding_principal_interest_fees` | 3,142,587,200 CNY | same | page 4, “资产池特征/资产池未偿本息费余额” | pass |

## Notes

- The CNY value is converted deterministically from the report's `314,258.72 万元`.
- The extractor accepts exactly one candidate in the verified local `资产池特征` context; otherwise it returns no fact.
- The extractor explicitly skips `ocr_requested` pages. The companion 中债资信 rating report is pure scan under native parsing and correctly returns no fact; it remains an OCR validation item.
