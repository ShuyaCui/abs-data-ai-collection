# Twelve-field vertical-slice progress — 2026-08-22

This is a development coverage matrix, not a frozen gold set. “CLI verified” means the real sample passed secure intake, parsing, fact persistence and evidence emission.

| # | Field | Status | Current evidence |
|---:|---|---|---|
| 1 | `security_code` | CLI verified | OCR issuance-result announcement, `2689075` / `2689076` |
| 2 | `asset_full_name` | CLI verified | native issuance announcement, page-1 title |
| 3 | `issue_rating` | pending | needs product-to-security association plus rating-report security disposition |
| 6 | `initial_cutoff_date` | CLI verified | native issuance announcement, page 2 |
| 7 | `maturity_date` | CLI verified | OCR issuance-result announcement, tranche tables |
| 12 | `tranche_issue_amount` | CLI verified | OCR issuance-result announcement, actual issuance amounts |
| 14 | `tranche_current_balance` | pending | needs report effective-date/threshold logic and security association |
| 15 | `initial_pool_outstanding_principal_interest_fees` | function-level only | native CCXI report; secure CLI quarantines its `/URI` action |
| 19 | `first_interest_payment_date` | pending | needs scheduled/adjusted/actual-date semantics and security association |
| 25 | `latest_report_date` | CLI verified | fourth trustee report, page 1 |
| 35 | `npl_trustee_recovery_cash` | CLI verified | fourth trustee report, pages 7 inputs and versioned derivation |
| 39 | `cashflow_collection_table` | pending | native-x86 PP-Structure table/cell-coordinate preflight remains open |

## Current score

- CLI verified: 6/12.
- Function-level only: 1/12.
- Pending: 5/12.
- Secure product rating-report route: blocked only by a policy decision on quarantined `/URI` links; no action is executed and no bypass exists.

## Next non-model work

1. Decide whether a quarantined PDF with an allowlisted `https`/`http` URI may be sanitized into a derived, hash-linked parsing copy, or must remain rejected.
2. On native x86, validate table/cell coordinates for the PP-Structure container before emitting field 39 or using its output for security/tranche association.
