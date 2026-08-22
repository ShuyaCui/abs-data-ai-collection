# Gold evaluation contract — 2026-08-22

The repository now contains a credential-free evaluator and JSON schema at `evaluation/gold.schema.json`. Each gold row binds one expected field to its case, product split, entity, status, normalized value, effective date and complete evidence-ID set.

The evaluator deliberately rejects product leakage between `development`, `validation` and `holdout`. It reports exact fact matches, exact evidence-set matches, false fills for expected non-disclosure/not-applicability or unexpected disclosed/derived outputs, and critical-field failures. The schema enumerates the current 42 field IDs, rejects non-null values with an empty evidence set, and has a regression check against the field contract. Runtime loading reconstructs the same field-contract validation for entity grain, status and value shape. It contains no model call and no sample-document labels; the business data owner must provide and sign the first frozen gold JSONL before model selection or auto-confirmation is considered.

Synthetic acceptance checks: exact disclosed match plus an expected-not-disclosed false fill; unexpected critical output; product split leakage; rejection of undeclared/unknown fields and malformed non-null gold facts. Full offline suite: 94 passed, 1 explicit parser skip.
