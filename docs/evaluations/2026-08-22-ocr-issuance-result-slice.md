# OCR issuance-result slice — 2026-08-22

## Scope

Scanned `臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf`, parsed locally with Docling OCR; no model API call.

| Security | Field | Expected | Extracted | Evidence | Result |
|---|---|---:|---:|---|---|
| 2689075 | `security_code` | 2689075 | same | p1 table label/value | pass |
| 2689075 | `maturity_date` | 2028-02-23 | same | p1 table label/value | pass |
| 2689075 | `tranche_issue_amount` | 1.32 CNY_100M | same | p1 actual issuance amount | pass |
| 2689075 | `tranche_level` | 优先档 | same | p1 security-name label/value | pass |
| 2689076 | `security_code` | 2689076 | same | p2 table label/value | pass |
| 2689076 | `maturity_date` | 2029-04-23 | same | p2 table label/value | pass |
| 2689076 | `tranche_issue_amount` | 0.5 CNY_100M | same | p2 actual issuance amount | pass |
| 2689076 | `tranche_level` | 次级档 | same | p2 security-name label/value | pass |

## Safeguards

- Accept only an issuance-result announcement whose first non-empty OCR block is the first-page product title.
- Every OCR page containing one of the three tranche-table labels must contain exactly one adjacent label/value pair for code, expected maturity, and actual issuance amount; any incomplete or duplicate row rejects the whole document.
- `tranche_level` is emitted only when exactly one adjacent `证券名称` value contains exactly one of `优先档` or `次级档` and its label precedes the verified `证券代码` label by at most six OCR blocks. This binds it to the same record layout; missing, ambiguous, or distant values remain blank.
- Every fact retains the title and its parser-owned table label and value blocks.
