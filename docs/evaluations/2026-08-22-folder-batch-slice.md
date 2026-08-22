# Folder batch extraction slice — 2026-08-22

## Scope

`npl-extract extract-folder` is the local, one-folder candidate route. It runs only deterministic extractors and makes no model or network call.

## Safety and selection contract

- The output must be an `.xlsx` outside the source directory.
- `--product-key` is an external identifier; the required `--product-name` binds the source filenames to the business-confirmed product identity.
- Every source document receives a raw SHA-256 in the batch manifest.
- A duplicate issuance announcement/result/prospectus, conflicting product identity, tied trustee maximum period, or unparseable trustee period is `ambiguous` and not extracted.
- Trustee selection considers only security-inspected (`queued`) reports; an unsafe newer file is `rejected` and cannot suppress an older safe report.
- A parser/staging failure is isolated to that document as `failed` with an error code; the remaining documents are still exported.
- Direct source facts are content-addressed per document. Derived facts are content-addressed under `batch_sha256`; their manifest path is the canonical review input.

## Regression evidence

The focused CLI/export/evaluation suite passed `40` tests. The full suite passed `143` tests with `1` explicit skip. Dedicated regressions cover parser-failure continuation, duplicate document roles, mixed product names (including an identity difference after “不良资产”), tied trustee periods, rejected newer trustee reports, template/output collision, output-lock contention, and output-inside-input rejection.

## Real sample run

Command:

```bash
.venv/bin/npl-extract extract-folder \
  'data/臻粹2026年第二期不良资产证券_测试样例2' \
  --product-key 'product:臻粹2026-2' \
  --product-name '臻粹2026年第二期不良资产' \
  --template 'data/42字段（测试）.xlsx' \
  --output 'runs/sample/folder-candidate-extraction-v3.xlsx' \
  --runs-dir 'runs/sample/folder-batch-runs-v3'
```

Result: `32` candidate facts; `4` documents `processed`; trustee periods 1–3 `superseded`; `3` documents `unsupported`; no failures or ambiguity. The manifest records all ten source hashes, the chosen fourth trustee report, per-document evidence/fact artifacts, batch SHA-256 `47d5d9277622b50b0ca33b11ad97450b24c391c6daa3fa9736e7f20eedb3a7c6`, and the canonical derived-fact artifact.

Workbook structural inspection: five worksheets (`product`, `report`, two `security`, `证据`), `118` evidence rows, zero formulas and zero Excel error values. This confirms export integrity only; it is not a business-value accuracy score because no signed gold set exists.

## Independent review

A second independent review found and verified fixes for trustee selection, product binding, per-document failure isolation, immutable derived artifacts, template/output collision, and concurrent output publication. Final review found no blocker or important issue. Ponytail review: `Lean already. Ship.`
