# Twelve-field MVP-v0 progress — 2026-08-23

This is a development coverage matrix, not a frozen gold set. “CLI verified” means the real sample passed secure intake, parsing, fact persistence and evidence emission.

| # | Field | Status | Current evidence |
|---:|---|---|---|
| 1 | `security_code` | CLI verified | OCR issuance-result announcement, `2689075` / `2689076` |
| 2 | `asset_full_name` | CLI verified | native issuance announcement, page-1 title |
| 3 | `issue_rating` | CLI verified | native prospectus p2 two-agency table, projected through explicit OCR tranche associations; rating reports remain higher-precedence when safely available |
| 6 | `initial_cutoff_date` | CLI verified | native issuance announcement, page 2 |
| 7 | `maturity_date` | CLI verified | OCR issuance-result announcement, tranche tables |
| 12 | `tranche_issue_amount` | CLI verified | OCR issuance-result announcement, actual issuance amounts |
| 14 | `tranche_current_balance` | CLI verified | fourth trustee report: page 6 code/balance row, effective 2026-08-24 payment date on page 5 |
| 15 | `initial_pool_outstanding_principal_interest_fees` | CLI verified | native CCXI report p4; inert `https` annotation admitted without permitting chained or executable actions |
| 19 | `first_interest_payment_date` | CLI verified | issuance prospectus p2 contractual first payment date, projected through explicit OCR tranche associations |
| 25 | `latest_report_date` | CLI verified | fourth trustee report, page 1 |
| 35 | `npl_trustee_recovery_cash` | CLI verified | fourth trustee report, pages 7 inputs and versioned derivation |
| 39 | `cashflow_collection_table` | BLOCKED | code/fixture contract covers cells, 37 monthly rows, disclosed total and rounding tolerance; native-x86 PP-Structure preflight remains open |
| 40 | `unit_remaining_face_value` | function-level verified | actual issuance amount + prospectus p120/p121 initial face value + fourth trustee-report balance, effective 2026-08-24 |

## Current score

- CLI verified: 11/12.
- Blocked by native-x86 runtime validation: 1/12.

## Next non-model work

1. On native x86, validate PP-Structure table/cell coordinates for p112–113 before emitting Field 39 for the real product bundle.
