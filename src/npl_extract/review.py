from __future__ import annotations

from datetime import datetime

from npl_extract.contracts import ExtractionFact, ReviewAction, ReviewDecision


def review_fact(
    candidate: ExtractionFact,
    *,
    action: ReviewAction,
    decision_id: str,
    reviewer_id: str,
    reason_code: str,
    decided_at: datetime,
    corrected_fact: ExtractionFact | None = None,
) -> ReviewDecision:
    """Create one immutable human-review decision for a provisional candidate."""
    if candidate.confirmed:
        raise ValueError("confirmed facts cannot be reviewed again")
    if action is ReviewAction.CORRECT:
        if corrected_fact is None or (corrected_fact.field_id, corrected_fact.entity_key) != (candidate.field_id, candidate.entity_key):
            raise ValueError("corrected fact must keep the candidate field and entity")
        if not corrected_fact.confirmed:
            raise ValueError("corrected fact must be confirmed")
        if corrected_fact.fact_id == candidate.fact_id:
            raise ValueError("corrected fact must have a new fact ID")
        resolved_fact = corrected_fact
    elif action is ReviewAction.ACCEPT:
        resolved_fact = ExtractionFact.model_validate(
            {**candidate.model_dump(mode="python"), "fact_id": f"confirmed:{candidate.fact_id}:{decision_id}", "confirmed": True}
        )
    else:
        if corrected_fact is not None:
            raise ValueError("rejected facts cannot include a correction")
        resolved_fact = None
    return ReviewDecision(
        decision_id=decision_id,
        candidate_fact_id=candidate.fact_id,
        action=action,
        reviewer_id=reviewer_id,
        reason_code=reason_code,
        decided_at=decided_at,
        resolved_fact=resolved_fact,
    )
