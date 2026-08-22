# Excel export slice — 2026-08-22

## Scope

The original `data/42字段（测试）.xlsx` template was projected from 13 real candidate facts persisted by the secure CLI:

| Entity worksheet | Non-empty template fields |
|---|---:|
| `product_sample` | 3 |
| `report_sample` | 2 |
| `security_2689075` | 3 |
| `security_2689076` | 3 |

The companion `证据` worksheet has 28 evidence rows plus its header. It records entity, field, status, candidate value, report name, physical page, table/paragraph locator, evidence ID and original parser text.

## Validation

- The export command reads persisted fact JSONL only; it does not read or parse PDFs.
- All 42 template rows remain present for every entity. Missing facts remain blank.
- Cross-entity leakage was caught in a real output and fixed: all entity sheets are created from the empty template before any values are written.
- Repeated field candidates for the same entity cause the export to fail instead of silently selecting one.
- Only `disclosed` and `derived` facts can populate the main template. An `ambiguous` candidate may remain in the evidence worksheet, but its main value cell stays blank.
- The shared fact contract enforces the entity-key prefix for every field grain (`product:`, `security:`, `report:`, or `cashflow_row:`); malformed persisted JSONL is rejected by the export CLI with JSON error output and exit code 2.
- This is a candidate-fact workbook, not an auto-confirmed business deliverable.
