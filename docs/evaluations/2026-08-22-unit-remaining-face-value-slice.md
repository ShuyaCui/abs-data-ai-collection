# Unit remaining face value slice — 2026-08-22

This is a local, cross-document deterministic derivation. No model call or document egress occurred.

| Security | Formula | Result | Effective date | Evidence |
|---|---|---:|---|---|
| `2689075` (优先档) | `0.839784 / 1.32 × initial_face_value(100)` | `63.62` CNY | `2026-08-24` | 《簿记建档发行结果公告》p1 `实际发行总额 13,200.00万元`; 《发行说明书》p120 initial face value `100元`; 《第4期受托机构报告》p5 payment date and p6 post-payment principal `83,978,400.00` |
| `2689076` (次级档) | `0.5 / 0.5 × initial_face_value(100)` | `100.00` CNY | `2026-08-24` | 《簿记建档发行结果公告》p2 `实际发行总额 5,000.00万元`; 《发行说明书》p121 initial face value `100元`; 《第4期受托机构报告》p5 payment date and p6 post-payment principal `50,000,000.00` |

`derive_unit_remaining_face_values` accepts only one disclosed positive `tranche_issue_amount`, `tranche_current_balance`, and `tranche_initial_face_value` for every same `security:<code>` key. It rejects duplicate, missing, non-finite, negative, above-initial, zero-denominator, mismatched-security, or mixed-effective-date inputs. Output is CNY, rounded to two decimal places with `ROUND_HALF_UP`, and is `derived`, preserving all three input evidence sets and IDs under rule version `unit-remaining-face-value-v1`.

The result is intentionally function-level until the cross-document fact-assembly operation is added. The existing single-document CLI must not pretend a derived candidate belongs to only one input document.
