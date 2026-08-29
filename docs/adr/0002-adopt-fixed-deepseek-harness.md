# ADR 0002: Adopt a Fixed DeepSeek Harness Release

- Status: Superseded
- Date: 2026-08-21
- Decision owner: Project owner

## Superseded decision

This exploratory decision is no longer the production default. The current production path is **方案 A：确定性 Python workflow + 按需的一次性 Qwen Semantic Worker + 独立 `ReviewDecision`**; it has no Agent loop or Harness control plane. The durable evidence, fact and review contracts remain unchanged.

Only a frozen validation set and real failure cases may justify reconsidering a bounded multi-round evidence-tool loop (方案 B) or Pi Agent Core. The required evidence is a material quality gain over the one-shot call, measured together with evidence completeness, false fill, P95 latency, token cost and runtime failure rate. See [the current production plan](../2026-08-28-abs-data-ai-collection-feasibility-and-production-plan-complete.md).

The remainder of this ADR is retained as the historical rationale for the former DeepSeek Harness experiment.

## Context

The document-extraction workflow needs one control plane for bounded agent decisions, tool policy, human review, approvals, session traces and feedback-driven iteration. It must remain compatible with a Python Docling/PaddleOCR data plane, provider-neutral field/evidence contracts and external distributed scheduling.

Pi Agent is the lower-complexity fallback, while Prime Agent adds persistent IPython, recursive agents and self-modifying Continual Harness behavior that is too permissive for the regulated production path. DeepSeek Harness provides the closest structural fit through typed tools, append-only session events, human-question and approval seams, sandbox policies, Python SDK integration and replaceable plugins.

DeepSeek Harness is still a developer preview and explicitly permits breaking changes. The current immutable release is `dsh-v0.1.0-rc.8`, commit `141eb6fef83422698aef7a981029e843e8161534`.

## Decision

1. Use DeepSeek Harness `dsh-v0.1.0-rc.8` at commit `141eb6fef83422698aef7a981029e843e8161534` as the initial unified control-plane runtime.
2. Pin the tag, full commit, resolved package versions and runtime artifact hashes. Production must never follow `master` or an unpinned release range.
3. DeepSeek Harness owns bounded agent/session execution, tool registration, human questions, one-shot approval, permissions and operational trace events.
4. Python workers own native PDF parsing, OCR, evidence geometry, deterministic normalization/calculation and Pydantic validation.
5. `Evidence`, `ExtractionFact`, `ReviewDecision`, `ReviewFeedback` and `WorkflowVersion` are the authoritative business records. Harness session formats are replaceable operational records.
6. The default production policy is local parsing/OCR/retrieval, no full-document model egress, fragment-only approved model calls, `workspace-write + ask`, tool allowlisting and locally retained/redacted telemetry.
7. Feedback refinement runs in `propose_only` mode. No agent may directly update an active prompt, skill, rule, field contract or global memory. Promotion requires frozen-gold replay, regression gates and business data-owner approval.
8. DeepSeek Harness `jobs-local` is not used as the distributed document queue. Workload tiers use an external durable execution plane when multi-host scheduling is justified.

## Consequences

### Positive

- Human interaction, approvals, session events and tool policy share one runtime.
- The Python parsing stack remains intact.
- Field, evidence and review data remain independent of Harness and model vendors.
- A later model, queue or storage migration does not require rewriting the business contracts.

### Negative

- The project accepts dependency on a developer-preview runtime.
- The team must maintain a pinned internal runtime and explicit migration tests.
- DeepSeek Harness and its Python SDK add a subprocess/runtime boundary.
- Distributed scheduling still requires an external queue and worker control plane.

## Upgrade policy

An upgrade requires all of the following:

1. explicit old/new version and storage-format review;
2. session replay and business-record migration tests;
3. the frozen gold set passing all critical field and evidence gates;
4. security, egress and permission-policy regression checks;
5. load comparison for latency, memory and cost;
6. business data-owner approval and a documented rollback target.

## Rollback

If the pinned runtime blocks the 12-field PoC through incompatible session/schema behavior, unacceptable worker density or excessive Cordis integration cost, revert the control plane to Pi Agent while retaining the same business schemas and Python worker APIs.

## Sources

- [DeepSeek Harness immutable `dsh-v0.1.0-rc.8` release](https://github.com/deepseek-ai/deepseek-harness/releases/tag/dsh-v0.1.0-rc.8)
- [Pinned release commit](https://github.com/deepseek-ai/deepseek-harness/commit/141eb6fef83422698aef7a981029e843e8161534)
- [DeepSeek Harness developer-preview notice](https://github.com/deepseek-ai/deepseek-harness#developer-preview)
- [DeepSeek Harness Python SDK](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/python-sdk.md)
- [DeepSeek Harness jobs contract](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/jobs.md)
