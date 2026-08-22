# Prospectus first-payment association slice — 2026-08-22

## Scope

The secure CLI parsed only page 2 of the native-text `臻粹2026年第二期不良资产支持证券发行说明书.pdf`. It was given the persisted OCR fact set from the matching issuance-result announcement through `--association-facts`; it did not infer security identity from a filename alone and made no model call.

| Security | `tranche_level` association | Extracted `first_interest_payment_date` | Direct source | Association source | Result |
|---|---|---|---|---|---|
| `2689075` | 优先档 | `2026-05-23` | issuance prospectus p2, “资产支持证券的第一个支付日是 …” | issuance-result announcement p1, `证券名称` | pass |
| `2689076` | 次级档 | `2026-05-23` | issuance prospectus p2, same sentence | issuance-result announcement p2, `证券名称` | pass |

## Safeguards

- The association input is explicit JSONL of already contract-validated facts; malformed JSON or fact-contract violations stop the CLI with JSON error output and exit code 2.
- Every accepted association must be a unique `disclosed` `tranche_level` fact on a `security:` entity, with issuance-result evidence whose normalized product name exactly equals the prospectus product name. Both directions are unique: one level maps to one security and one security maps to one level.
- The prospectus must contain exactly one valid native-text first-payment date. OCR pages, invalid dates, duplicate dates, missing associations, duplicate levels, and cross-product facts yield no candidate fact.
- The emitted date is the contractually stated first payment date (`2026-05-23`), not an inferred business-day-adjusted or actual payment date. Those remain separate time semantics for later work.
