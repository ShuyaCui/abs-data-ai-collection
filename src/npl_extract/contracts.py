from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, StrictBool, model_validator


class FactStatus(str, Enum):
    DISCLOSED = "disclosed"
    DERIVED = "derived"
    NOT_APPLICABLE = "not_applicable"
    NOT_DISCLOSED = "not_disclosed"
    AMBIGUOUS = "ambiguous"
    PENDING_DEFINITION = "pending_definition"


class ReviewAction(str, Enum):
    ACCEPT = "accept"
    CORRECT = "correct"
    REJECT = "reject"


class ValuePolicy(str, Enum):
    DIRECT_ONLY = "direct_only"
    DIRECT_OR_DERIVED = "direct_or_derived"
    DERIVED_ONLY = "derived_only"


_ENTITY_KEY_PREFIXES = {
    "product": "product:",
    "tranche": "security:",
    "report": "report:",
    "cashflow_row": "cashflow_row:",
}
_ENTITY_KEY_LABELS = {"tranche": "security"}


class EvidenceRef(BaseModel):
    evidence_id: str
    artifact_scope: str
    document_name: str
    physical_page: int = Field(ge=1)
    locator: str
    exact_text: str


class FactInput(BaseModel):
    fact_id: str
    confirmed: bool


class FieldContract(BaseModel):
    contract_version: str
    field_id: str = Field(alias="id")
    export_name: str
    entity_grain: str
    value_type: str
    unit: str | None
    critical: bool
    pending_definition: bool = False
    value_policy: ValuePolicy
    allowed_statuses: frozenset[FactStatus]
    source_families: tuple[str, ...]
    source_precedence: tuple[str, ...]


class ExtractionFact(BaseModel):
    fact_id: str
    field_id: str
    entity_key: str
    status: FactStatus
    value: str | StrictBool | list[str] | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    effective_at: date | None = None
    rule_version: str | None = None
    derived_inputs: list[FactInput] = Field(default_factory=list)
    confirmed: bool = False

    @model_validator(mode="after")
    def enforce_fact_contract(self) -> ExtractionFact:
        contract = _load_all_field_contracts().get(self.field_id)
        if contract is None:
            raise ValueError("unknown field")
        if self.status not in contract.allowed_statuses:
            raise ValueError(f"field {self.field_id} does not allow status {self.status.value}")
        if contract.value_type == "boolean" and self.value is not None and type(self.value) is not bool:
            raise ValueError("boolean facts require a boolean value")
        if contract.value_type != "boolean" and type(self.value) is bool:
            raise ValueError("only boolean fields may carry a boolean value")
        if contract.value_type == "string[]" and self.value is not None and (
            not isinstance(self.value, list) or not self.value or not all(isinstance(item, str) and item for item in self.value)
        ):
            raise ValueError("string[] facts require a non-empty string array")
        if contract.value_type != "string[]" and isinstance(self.value, list):
            raise ValueError("only string[] fields may carry an array value")
        if self.status is FactStatus.DISCLOSED and (self.value is None or not self.evidence):
            raise ValueError("disclosed facts require a value and evidence")
        if self.status is FactStatus.DERIVED:
            if self.value is None or not self.rule_version or not self.derived_inputs:
                raise ValueError("derived facts require a value, rule version, and inputs")
            if self.confirmed and not all(item.confirmed for item in self.derived_inputs):
                raise ValueError("confirmed derived facts require confirmed inputs")
        if self.status in {FactStatus.NOT_APPLICABLE, FactStatus.NOT_DISCLOSED} and self.value is not None:
            raise ValueError("not-applicable and not-disclosed facts must not carry a value")
        prefix = _ENTITY_KEY_PREFIXES.get(contract.entity_grain)
        if prefix and not self.entity_key.startswith(prefix):
            label = _ENTITY_KEY_LABELS.get(contract.entity_grain, contract.entity_grain)
            raise ValueError(f"{contract.entity_grain} facts require a {label} key")
        return self


class ReviewDecision(BaseModel):
    decision_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    candidate_fact_id: str
    action: ReviewAction
    reviewer_id: str = Field(min_length=1)
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    decided_at: datetime
    resolved_fact: ExtractionFact | None = None

    @model_validator(mode="after")
    def enforce_review_contract(self) -> ReviewDecision:
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ValueError("review decisions require a timezone-aware timestamp")
        if self.action is ReviewAction.REJECT and self.resolved_fact is not None:
            raise ValueError("rejected facts cannot have a resolved fact")
        if self.action in {ReviewAction.ACCEPT, ReviewAction.CORRECT} and (
            self.resolved_fact is None or not self.resolved_fact.confirmed
        ):
            raise ValueError("accepted and corrected facts require a confirmed resolved fact")
        return self


_STATUSES_BY_POLICY = {
    ValuePolicy.DIRECT_ONLY: frozenset(
        {FactStatus.DISCLOSED, FactStatus.NOT_APPLICABLE, FactStatus.NOT_DISCLOSED, FactStatus.AMBIGUOUS}
    ),
    ValuePolicy.DIRECT_OR_DERIVED: frozenset(
        {FactStatus.DISCLOSED, FactStatus.DERIVED, FactStatus.NOT_APPLICABLE, FactStatus.NOT_DISCLOSED, FactStatus.AMBIGUOUS}
    ),
    ValuePolicy.DERIVED_ONLY: frozenset(
        {FactStatus.DERIVED, FactStatus.NOT_APPLICABLE, FactStatus.NOT_DISCLOSED, FactStatus.AMBIGUOUS}
    ),
}


@lru_cache(maxsize=1)
def load_field_contracts() -> dict[str, FieldContract]:
    return _load_contracts(include_supporting=False)


@lru_cache(maxsize=1)
def _load_all_field_contracts() -> dict[str, FieldContract]:
    return _load_contracts(include_supporting=True)


def _load_contracts(*, include_supporting: bool) -> dict[str, FieldContract]:
    path = Path(__file__).parents[2] / "config" / "fields.v1.json"
    document = json.loads(path.read_text())
    fields = []
    items = document["fields"]
    if include_supporting:
        items += document.get("supporting_fields", [])
    for item in items:
        field = {**document["defaults"], **item, "contract_version": document["version"]}
        policy = ValuePolicy(field["value_policy"])
        field["allowed_statuses"] = _STATUSES_BY_POLICY[policy] | (
            {FactStatus.PENDING_DEFINITION} if field.get("pending_definition") else set()
        )
        fields.append(FieldContract.model_validate(field))
    return {field.field_id: field for field in fields}
