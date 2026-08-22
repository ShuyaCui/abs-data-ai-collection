# Static-pool / revolving-purchase slice — 2026-08-22

Command: `npl-extract extract <发行说明书> --entity-key product:臻粹2026-2 --pages 90-90` using the local `pypdf` parser. No model call or document egress occurred.

| Field | Value | Source evidence |
|---|---|---|
| `has_revolving_purchase` | `false` (boolean) | p90 “资产池将是一个静态池” plus the immediately following “将不会购买其他资产…或以其他资产替换已有资产” paragraph blocks |

Matching treats full-width quotation marks as layout noise but retains the original parser-owned text. It requires exactly one native two-block disclosure containing all three conditions: static pool, no purchase of additional assets and no replacement of existing assets. Missing, duplicate or OCR-only candidates remain blank.

The shared fact, frozen-gold and Excel contracts now carry native booleans; the Excel projection renders `false` as lowercase text.
