# Execution log

## 2026-08-21 — MVP foundation

- Added a Python package, local virtual environment configuration, and offline tests.
- Implemented PDF intake checks: PDF signature, size/page limits, encryption, active content, embedded files, input-root containment, and SHA-256 identity.
- Frozen 42 field contracts in `config/fields.v1.json`; fields 4, 5, and 42 remain explicitly `pending_definition`.
- Implemented page routing and content-addressed evidence artifacts using synthetic page inputs.
- Implemented the accepted NPL recovery rule: `处置中累计回收 + 处置完毕累计回收`, excluding other income and qualified investments, before disposal expenses.
- Verified 15 offline tests pass.
- Downloaded and SHA-512 checked `@deepseek-ai/dsh@0.1.0-rc.8` with `npm pack`. The matching GitHub release exists, while the published Python SDK is only `rc.7`; the implementation will not substitute it for the approved `rc.8` runtime.
