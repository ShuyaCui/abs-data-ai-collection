# Execution log

## 2026-08-21 — MVP foundation

- Added a Python package, local virtual environment configuration, and offline tests.
- Implemented PDF intake checks: PDF signature, size/page limits, encryption, active content, embedded files, input-root containment, and SHA-256 identity.
- Frozen 42 field contracts in `config/fields.v1.json`; fields 4, 5, and 42 remain explicitly `pending_definition`.
- Implemented page routing and content-addressed evidence artifacts using synthetic page inputs.
- Implemented the accepted NPL recovery rule: `处置中累计回收 + 处置完毕累计回收`, excluding other income and qualified investments, before disposal expenses.
- Verified 15 offline tests pass.
- Downloaded and SHA-512 checked `@deepseek-ai/dsh@0.1.0-rc.8` with `npm pack`. The matching GitHub release exists, while the published Python SDK is only `rc.7`; the implementation will not substitute it for the approved `rc.8` runtime.

## 2026-08-22 — Safe local parsing and route evaluation

- Initialized Git branch `dev` and committed the foundation as `557da93`.
- Installed the lockfile-pinned DeepSeek Harness and verified `dsh --version` is `0.1.0-rc.8`.
- Repaired the page-artifact completion invariant: incomplete or stale-version artifacts are regenerated rather than reused.
- Added a local CLI: `npl-extract inspect` and `npl-extract parse`.
- Added native-text parsing through `pypdf` as a geometry-free fallback and tightened the native-text gate to eight useful characters.
- Added a test rejecting annotation `/Launch` actions.
- Evaluated routing on 751 real sample pages; see `docs/evaluations/2026-08-22-page-routing-sample.md`.
- Extracted and value-checked the first deterministic trustee-report slice: `最新报告日期` and `NPL-受托已回收（亿）`. Both remain provisional until geometry-capable parser evidence is available.
- Made artifact writes safe for concurrent attempts by using a unique temporary file for each atomic replace; added a two-writer regression test.
- Persisted the two disclosed inputs behind field 35 (`处置中累计回收金额` and `处置完毕累计回收金额`) as supporting facts before deriving the exported amount. Candidate fact sets are immutable, content-addressed JSONL artifacts. The extractor now refuses non-trustee documents and invalid dates.
- Moved the native fallback parse out of the CLI process and added CPU/output-size limits plus a wall-clock timeout. Container-level network isolation and memory limits remain production deployment requirements.
- Added the optional `parser` dependency set with Docling 2.121.0. RapidOCR local weights downloaded successfully; Docling's table-model download is incomplete in the current network environment, so geometry/table validation remains pending.
- Verified the Docling native-text adapter with OCR and table reconstruction disabled: the 13-page fourth trustee report produced 725 coordinate-bearing blocks. The unavailable table-model remains required before emitting table-cell evidence.
- Added a fixed-DSH headless policy patch that disables general shell, filesystem, web and subagent tools, forces read-only mode and disables telemetry egress. Dedicated local document-worker tools remain the next Harness integration step.
