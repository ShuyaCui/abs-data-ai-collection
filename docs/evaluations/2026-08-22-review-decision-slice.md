# Review-decision slice — 2026-08-22

This offline evaluation checks the immutable human-review domain operation. It does not represent a business sign-off: no sample fact was accepted, corrected, or rejected on behalf of the business data owner.

| Gate | Result | Evidence |
|---|---|---|
| Candidate preservation | pass | Accept creates a new `confirmed:` fact; the proposal remains unchanged. |
| Correction integrity | pass | A correction must retain the candidate field and entity, use a new fact ID, and be itself confirmed. |
| Derived-fact integrity | pass | Accepting a derived fact with provisional inputs fails contract validation. |
| Idempotent append | pass | Replaying a decision ID with only a new attempt timestamp reuses the original JSON event; any other payload difference fails. |
| CLI audit boundary | pass | `npl-extract review` accepts only hash-verified JSONL fact artifacts directly beneath the specified document’s run directory; cross-document and tampered paths fail. |
| CLI boundary | pass | The CLI loads that persisted candidate, invokes the same domain operation, and writes one immutable review event. |

The event contains reviewer ID, uppercase reason code, timezone-aware decision time, candidate fact ID and, for accept/correct, the new confirmed fact. It is independent of the DeepSeek Harness transcript; the later DSH user-question/approval tool must call this operation rather than writing business records itself.

Verification: `pytest tests/test_review.py tests/test_cli.py -q` and full offline `pytest -q`: 87 passed, 1 explicit parser skip.
