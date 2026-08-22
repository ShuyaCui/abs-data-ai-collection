from __future__ import annotations

from datetime import UTC, datetime

import pytest

from npl_extract.contracts import EvidenceRef, ExtractionFact, FactInput, FactStatus
from npl_extract.pipeline import persist_review_decision
from npl_extract.review import ReviewAction, review_fact


def _fact(*, field_id: str = "asset_full_name", entity_key: str = "product:test") -> ExtractionFact:
    return ExtractionFact(
        fact_id="candidate-1",
        field_id=field_id,
        entity_key=entity_key,
        status=FactStatus.DISCLOSED,
        value="臻粹不良资产支持证券",
        evidence=[
            EvidenceRef(
                evidence_id="p001:b001",
                artifact_scope="pypdf-all",
                document_name="发行公告.pdf",
                physical_page=1,
                locator="公告标题",
                exact_text="臻粹不良资产支持证券发行公告",
            )
        ],
    )


def test_accept_creates_a_new_confirmed_fact_without_mutating_candidate() -> None:
    candidate = _fact()

    decision = review_fact(
        candidate,
        action=ReviewAction.ACCEPT,
        decision_id="review-001",
        reviewer_id="business-owner:alice",
        reason_code="VALUE_AND_EVIDENCE_CONFIRMED",
        decided_at=datetime(2026, 8, 22, tzinfo=UTC),
    )

    assert candidate.confirmed is False
    assert decision.action is ReviewAction.ACCEPT
    assert decision.resolved_fact is not None
    assert decision.resolved_fact.confirmed is True
    assert decision.resolved_fact.fact_id == "confirmed:candidate-1:review-001"
    assert decision.resolved_fact.value == candidate.value


def test_correction_requires_the_same_field_and_entity() -> None:
    candidate = _fact()
    correction = _fact(field_id="initial_cutoff_date")

    with pytest.raises(ValueError, match="field and entity"):
        review_fact(
            candidate,
            action=ReviewAction.CORRECT,
            decision_id="review-002",
            reviewer_id="business-owner:alice",
            reason_code="SOURCE_TEXT_CORRECTED",
            decided_at=datetime(2026, 8, 22, tzinfo=UTC),
            corrected_fact=correction,
        )


def test_correction_requires_a_new_fact_id() -> None:
    candidate = _fact()
    correction = ExtractionFact.model_validate({**candidate.model_dump(mode="python"), "confirmed": True})

    with pytest.raises(ValueError, match="new fact ID"):
        review_fact(
            candidate,
            action=ReviewAction.CORRECT,
            decision_id="review-002b",
            reviewer_id="business-owner:alice",
            reason_code="SOURCE_TEXT_CORRECTED",
            decided_at=datetime(2026, 8, 22, tzinfo=UTC),
            corrected_fact=correction,
        )


def test_accept_refuses_a_derived_fact_with_unconfirmed_inputs() -> None:
    candidate = ExtractionFact(
        fact_id="candidate-derived",
        field_id="npl_trustee_recovery_cash",
        entity_key="report:test",
        status=FactStatus.DERIVED,
        value="0.6040795674",
        evidence=_fact().evidence,
        rule_version="npl-recovery-cash-v1",
        derived_inputs=[FactInput(fact_id="input-1", confirmed=False)],
    )

    with pytest.raises(ValueError, match="confirmed"):
        review_fact(
            candidate,
            action=ReviewAction.ACCEPT,
            decision_id="review-003",
            reviewer_id="business-owner:alice",
            reason_code="VALUE_AND_EVIDENCE_CONFIRMED",
            decided_at=datetime(2026, 8, 22, tzinfo=UTC),
        )


def test_persists_an_idempotent_immutable_review_decision(tmp_path) -> None:
    decision = review_fact(
        _fact(),
        action=ReviewAction.ACCEPT,
        decision_id="review-004",
        reviewer_id="business-owner:alice",
        reason_code="VALUE_AND_EVIDENCE_CONFIRMED",
        decided_at=datetime(2026, 8, 22, tzinfo=UTC),
    )

    first = persist_review_decision("a" * 64, decision, tmp_path)
    second = persist_review_decision("a" * 64, decision, tmp_path)

    assert first.path.name == "review-004.json"
    assert first.reused is False
    assert second.reused is True
    assert first.path.read_text(encoding="utf-8").startswith('{"decision_id":"review-004"')

    retry = persist_review_decision(
        "a" * 64,
        decision.model_copy(update={"decided_at": datetime(2026, 8, 23, tzinfo=UTC)}),
        tmp_path,
    )
    assert retry.reused is True
    assert retry.decision.decided_at == decision.decided_at

    with pytest.raises(ValueError, match="different payload"):
        persist_review_decision("a" * 64, decision.model_copy(update={"reason_code": "SOURCE_TEXT_CORRECTED"}), tmp_path)
