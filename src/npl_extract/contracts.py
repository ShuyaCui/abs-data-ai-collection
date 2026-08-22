from __future__ import annotations

import json
from datetime import date
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class FactStatus(str, Enum):
    DISCLOSED = "disclosed"
    DERIVED = "derived"
    NOT_APPLICABLE = "not_applicable"
    NOT_DISCLOSED = "not_disclosed"
    AMBIGUOUS = "ambiguous"
    PENDING_DEFINITION = "pending_definition"


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
    value: str | None = None
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
