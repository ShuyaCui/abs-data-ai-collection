# Prospectus Recovery Slice and Deduplication Implementation Plan

> **For agentic workers:** REQUIRED: Use `superpowers:subagent-driven-development` (if subagents available) or `superpowers:executing-plans` to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic prospectus fields 36–38 and remove the three review-identified duplicate code shapes without changing general routing or other fields.

**Architecture:** A bounded native-text extractor accepts only p102–104 and emits evidence-backed product facts. Folder batch adds one fixed native range and suppresses only prospectus 36/37 when same-field rating-report facts already exist. Existing CLI and bridge modules receive local helper reuse only.

**Tech Stack:** Python 3.12, Pydantic domain facts, pytest; no new dependencies or model calls.

---

### Task 1: Add extraction tests and the deterministic recovery slice

**Files:**
- Modify: `tests/test_extract.py`
- Modify: `src/npl_extract/extract.py`

- [ ] Write failing tests for successful fields 36–38, missing adoption relation, conflicting Chinabond values, different units, extra same-structure rows, unbound agencies, same-value cross-page evidence, OCR/out-of-range rejection, and agencies without adoption. Assert every successful fact's product grain, `disclosed` status, exact value/unit, and complete evidence-ID set.
- [ ] Run the new tests; expect an import failure for `extract_prospectus_recovery_prediction_facts`.
- [ ] Implement the smallest extractor: native p102–104 only, explicit Chinabond label/value/relation checks, fail-closed unit matching, and parser-owned evidence.
- [ ] Run the targeted tests; expect pass.
- [ ] Commit the extraction slice.

### Task 2: Route the slice in CLI and preserve rating-report precedence

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/npl_extract/cli.py`

- [ ] Write a failing folder-batch test asserting the batch processes `rating_report` before `prospectus`, p102–104 is parsed with `pypdf`, and rating-report field 36 suppresses only prospectus field 36 (not 37 or 38).
- [ ] Run the test; expect failure because the range is absent.
- [ ] Reorder the two document roles, add the one p102–104 prospectus range, and filter only each conflicting prospectus field 36/37 candidate after same-field rating facts exist.
- [ ] Run the targeted CLI test; expect pass.
- [ ] Commit the batch route.

### Task 3: Remove the three duplicate code shapes

**Files:**
- Modify: `src/npl_extract/cli.py`
- Modify: `src/npl_extract/harness_bridge.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_harness_bridge.py`

- [ ] Write a failing CLI parser-option test and bridge tests covering equivalent block/cell truncation and canonical fact lookup.
- [ ] Run those tests; expect failure because the shared helpers do not exist.
- [ ] Add one shared CLI option helper, one bridge evidence-excerpt helper, and one canonical-fact lookup helper; retain `validate_facts` duplicate-ID rejection.
- [ ] Run targeted tests; expect pass.
- [ ] Commit the local deduplication.

### Task 4: Verify and document

**Files:**
- Modify: `docs/evaluations/2026-08-22-vertical-slice-progress.md`
- Modify: `docs/execution-log.md`

- [ ] Add a concise field 36–38 extraction record without claiming independent accuracy.
- [ ] Run `git diff --check` and `.venv/bin/python -m pytest -q`; expect clean diff and all tests passing.
- [ ] Request code review; fix Critical/Important findings.
- [ ] Commit the documentation and verification record.
