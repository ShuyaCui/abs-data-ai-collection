# Prospectus issue-rating association slice — 2026-08-22

## Scope

The secure CLI parsed page 2 of the native-text `臻粹2026年第二期不良资产支持证券发行说明书.pdf` with the matching issuance-result `tranche_level` fact set supplied explicitly through `--association-facts`. No rating-report PDF was parsed, no external model was called, and no document was sent outside the local process.

| Security | Extracted `issue_rating` (JSONL array) | Direct source | Association source | Result |
|---|---|---|---|---|
| `2689075` | `["中债资信:AAAsf","中诚信国际:AAAsf"]` | prospectus p2 “评级（中债资信/中诚信）” / 优先档 row | issuance-result p1 `证券名称` | pass |
| `2689076` | `["中债资信:无评级","中诚信国际:无评级"]` | prospectus p2 same header / 次级档 row | issuance-result p2 `证券名称` | pass |

The v1 field contract is `string[]`; each item preserves the agency and raw reported grade. The source page has no standalone rating-date cell, so no date is invented. “发行说明书” makes this an initial issuance candidate. A safely accepted rating report is a higher-precedence source and may supersede it under a future conflict resolver.

## Safeguards

- `string[]` facts are non-empty arrays of non-empty strings; all other field types reject array values. JSONL keeps arrays structured, while Excel main/evidence cells receive canonical compact JSON text.
- The rating header must be a unique native-text block containing `评级` followed within two blocks by `中债资信/中诚信`.
- Every associated tranche must have one and only one matching `优先档`/`次级档` row within the bounded rows after that header. A two-agency header paired with a single grade rejects the whole rating result rather than copying a value to the second agency.
- Product identity and bidirectional level/security uniqueness are enforced by the same association validator used by the first-payment field.
