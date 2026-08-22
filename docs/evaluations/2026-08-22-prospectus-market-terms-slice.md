# Prospectus market-and-issuance-method slice — 2026-08-22

Command: `npl-extract extract <发行说明书> --entity-key product:臻粹2026-2 --pages 3-3` using the local `pypdf` parser. No model call or document egress occurred.

| Field | Normalized value | Source evidence |
|---|---|---|
| `market` | `银行间债券市场` | p3: “本期资产支持证券拟采用公开簿记建档的方式在全国银行间债券市场发行” |
| `issuance_method` | `簿记建档` | p3 same sentence |

The normalized values follow the accepted definitions in `docs/research/0002-financial-field-definitions-and-decisions.md` (fields 21–22). The extractor requires exactly one native-text statement containing both the issuance method and market relation; absent, duplicated or OCR-only candidates return no fact.
