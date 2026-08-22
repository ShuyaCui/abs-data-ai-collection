# Issuance announcement deterministic slice — 2026-08-22

## Scope

One native-text sample: `臻粹2026年第二期不良资产支持证券发行公告.pdf`.

| Field | Expected | Extracted | Evidence | Result |
|---|---:|---:|---|---|
| `asset_full_name` | 臻粹2026年第二期不良资产支持证券 | same | page 1, announcement title | pass |
| `initial_cutoff_date` | 2026-01-26 | same | page 2, “初始起算日” | pass |
| `issue_amount_all_tranches` | 1.82 CNY_100M | same | page 1, “发行规模为 182,000,000.00 元” | pass |

## Metrics

- Value accuracy: 3/3.
- Evidence-page accuracy: 3/3.
- False fills: 0 in adversarial checks for a later-page/正文 title reference, a historical-product comparison, multiple candidate amounts in one or multiple blocks, and multiple initial cutoff dates in one or multiple blocks.
- Model calls and document egress: 0.

This is development evidence only, not a frozen product-level gold set. The remaining vertical-slice fields require tranche associations, rating-report OCR, current-report timing, or table evidence.
