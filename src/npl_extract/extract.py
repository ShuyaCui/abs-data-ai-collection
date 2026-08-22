from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from npl_extract.contracts import EvidenceRef, ExtractionFact, FactInput, FactStatus


@dataclass(frozen=True)
class RecoveryComponent:
    fact_id: str
    amount_cny: str
    evidence: EvidenceRef


def derive_npl_recovery_cash(
    *, entity_key: str, in_progress: RecoveryComponent, completed: RecoveryComponent
) -> ExtractionFact:
    """Calculate gross NPL recovery before expenses, excluding other cash inflows."""
    total_cny = Decimal(in_progress.amount_cny) + Decimal(completed.amount_cny)
    value_cny_100m = format(total_cny / Decimal("100000000"), "f")
    return ExtractionFact(
        fact_id=f"derived:npl-recovery:{in_progress.fact_id}:{completed.fact_id}",
        field_id="npl_trustee_recovery_cash",
        entity_key=entity_key,
        status=FactStatus.DERIVED,
        value=value_cny_100m,
        evidence=[in_progress.evidence, completed.evidence],
        rule_version="npl-recovery-cash-v1",
        derived_inputs=[
            FactInput(fact_id=in_progress.fact_id, confirmed=False),
            FactInput(fact_id=completed.fact_id, confirmed=False),
        ],
    )
