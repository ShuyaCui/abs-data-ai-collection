from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from npl_extract.contracts import EvidenceRef, ExtractionFact, FactInput, FactStatus, load_field_contracts


class GoldSplit(str, Enum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    HOLDOUT = "holdout"


class GoldFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(min_length=1)
    product_key: str = Field(pattern=r"^product:")
    split: GoldSplit
    field_id: str
    entity_key: str
    status: FactStatus
    value: str | StrictBool | list[str] | None
    effective_at: date | None
    evidence_ids: list[str]

    @model_validator(mode="after")
    def enforce_gold_contract(self) -> GoldFact:
        if self.field_id not in load_field_contracts():
            raise ValueError("unknown field")
        if self.value is not None and not self.evidence_ids:
            raise ValueError("non-empty gold facts require evidence IDs")
        evidence = [
            EvidenceRef(
                evidence_id=evidence_id,
                artifact_scope="gold",
                document_name="gold-reference",
                physical_page=1,
                locator="gold",
                exact_text="gold",
            )
            for evidence_id in self.evidence_ids[:1]
        ]
        ExtractionFact(
            fact_id="gold-contract-check",
            field_id=self.field_id,
            entity_key=self.entity_key,
            status=self.status,
            value=self.value,
            evidence=evidence,
            effective_at=self.effective_at,
            rule_version="gold-contract-v1" if self.status is FactStatus.DERIVED else None,
            derived_inputs=[FactInput(fact_id="gold-input", confirmed=False)] if self.status is FactStatus.DERIVED else [],
        )
        return self


@dataclass(frozen=True)
class EvaluationResult:
    total: int
    exact_fact_matches: int
    exact_evidence_matches: int
    false_fills: int
    critical_failures: int


def validate_gold_splits(gold: list[GoldFact]) -> None:
    splits_by_product: dict[str, set[GoldSplit]] = {}
    for fact in gold:
        splits_by_product.setdefault(fact.product_key, set()).add(fact.split)
    if any(len(splits) > 1 for splits in splits_by_product.values()):
        raise ValueError("a product cannot appear in more than one split")


def evaluate_case(gold: list[GoldFact], candidates: list[ExtractionFact]) -> EvaluationResult:
    validate_gold_splits(gold)
    expected = _unique_by_field_entity(gold)
    actual = _unique_by_field_entity(candidates)
    contracts = load_field_contracts()
    exact_facts = exact_evidence = false_fills = critical_failures = 0
    for key, target in expected.items():
        fact = actual.get(key)
        matches = fact is not None and (fact.status, fact.value, fact.effective_at) == (target.status, target.value, target.effective_at)
        if matches:
            exact_facts += 1
            if {evidence.evidence_id for evidence in fact.evidence} == set(target.evidence_ids):
                exact_evidence += 1
        if target.status in {FactStatus.NOT_DISCLOSED, FactStatus.NOT_APPLICABLE} and fact and fact.status in {FactStatus.DISCLOSED, FactStatus.DERIVED} and fact.value is not None:
            false_fills += 1
        if not matches and contracts[target.field_id].critical:
            critical_failures += 1
    for key, fact in actual.items():
        contract = contracts.get(fact.field_id)
        if key not in expected and contract and fact.status in {FactStatus.DISCLOSED, FactStatus.DERIVED} and fact.value is not None:
            false_fills += 1
            critical_failures += int(contract.critical)
    return EvaluationResult(len(expected), exact_facts, exact_evidence, false_fills, critical_failures)


def _unique_by_field_entity(facts: list[GoldFact] | list[ExtractionFact]) -> dict[tuple[str, str], GoldFact | ExtractionFact]:
    grouped = {(fact.field_id, fact.entity_key): fact for fact in facts}
    if len(grouped) != len(facts):
        raise ValueError("evaluation requires one fact per field and entity")
    return grouped
