# Actual-financing-entity slice — 2026-08-22

Command: `npl-extract extract <发行说明书> --entity-key product:臻粹2026-2 --pages 16-16` using the local `pypdf` parser. No model call or document egress occurred.

| Field | Value | Source evidence |
|---|---|---|
| `actual_financing_entity` | `["广发银行股份有限公司"]` | p16 “各参与机构名单 / 发起机构/贷款服务机构：广发银行股份有限公司” |

This follows the accepted definition that the actual financing entity is the sponsor, not the trustee/issuer. The extractor requires exactly one native participant-list heading plus a complete role listing. It returns no candidate for cover-page roles, generic mentions, duplicated/unclosed role text, mixed role prose, multiple companies, OCR pages or ambiguity.
