# MVP-v0 human review queue — 2026-08-23

Candidate output is ready for a business data owner; no decision has been made on the owner’s behalf.

- Workbook: `runs/sample/mvp-v0-candidate.xlsx` — filter the `证据` worksheet by entity and field to see report name, page, locator, evidence ID and exact text.
- Batch candidate file: `runs/sample/mvp-v0-candidate.jsonl`.
- Batch manifest: `runs/sample/mvp-v0-candidate.manifest.json`.

| Review group | Candidate fields/entities | Canonical input artifact | Primary evidence |
|---|---|---|---|
| Issuance announcement | asset full name; initial cutoff | `runs/sample/mvp-v0-runs/51c82411f6813f1db996fcfa6aac236ff8995d0f53946af80b7f43776d28d3db/facts/a274c64a96d1490c8387be78f0cccf131bb9b0f129b01f5f7edafaaab71a9f8a.jsonl` | 《发行公告》p1–2 |
| Issue result | security codes; maturity dates; tranche issue amounts | `runs/sample/mvp-v0-runs/eec62bc8ec34c19573fabdb84f282d9bae12767e2aa7c22c711e1e5a4de6202c/facts/a89849b749adbf361df7463ca539d26a24fdf93c3cb7b1c074dbe53b15c8be49.jsonl` | 《簿记建档发行结果公告》p1–2 |
| Prospectus | issue ratings; first payment dates | `runs/sample/mvp-v0-runs/ff3326e013da7376d0ead143c44ea797f662b8c0af6e2f0a85f773d5ed21a679/facts/b8629d2eab43b0ea7282eff8ca3f5b219b6b0ceee0e168b6e63e57678359ee75.jsonl` | 《发行说明书》p2 |
| CCXI rating report | initial pool outstanding principal/interest/fees | `runs/sample/mvp-v0-runs/797b1e6df3bf4f8e6081e2f0cc51cdfca762ed33c308070671e790c44f24b744/facts/85604c7ce98bb23769ea44ffc0878b32e0cc7c09bdbb4363259a4afd7f3d79d7.jsonl` | 《中诚信国际评级报告》p4 |
| Latest trustee report | latest report date; current balances; recovery components and derived NPL recovery | `runs/sample/mvp-v0-runs/17fe777e49011d9d6a835ea14e69cb0fe8d63caa6f77a1489663a31cdc823039/facts/cac5252383ca61db874768982ce318aac90759736e85bbfa7091a8c5a45fafd2.jsonl` | 《第4期受托机构报告》p1, p5–7 |
| Field 39 | cash-flow collection table | no candidate fact | `BLOCKED: PPSTRUCTURE_NATIVE_X86_PREFLIGHT_REQUIRED`; do not accept/reject as non-disclosure |

## Record a decision

Use the artifact matching the review group; it is content-addressed and must not be copied or edited. Replace the four bracketed values only after the reviewer has checked the workbook evidence.

```bash
.venv/bin/npl-extract review \
  --document-sha256 <document-sha256-from-manifest> \
  --facts <canonical-facts-artifact-from-table> \
  --fact-id <candidate-fact-id-from-candidate-jsonl> \
  --action accept \
  --decision-id <unique-lowercase-decision-id> \
  --reviewer-id <business-data-owner-id> \
  --reason-code VALUE_AND_EVIDENCE_CONFIRMED \
  --runs-dir runs/sample/mvp-v0-runs
```

For a correction, supply a separately reviewed `--corrected-fact`; for rejection, use `--action reject` and a business reason code. These operations append an immutable `ReviewDecision`; they never edit the candidate.

For `npl_trustee_recovery_cash`, accept the two supporting facts `disclosed:recovery-in-progress:p007:b028` and `disclosed:recovery-completed:p007:b029` first. The CLI then permits acceptance of the derived recovery fact only when both immutable input decisions are `accept`; a corrected input requires recalculation and does not automatically confirm the existing derived value.
