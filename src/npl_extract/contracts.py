from __future__ import annotations

import json
from datetime import date
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class FactStatus(str, Enum):
    DISCLOSED = "disclosed"
    DERIVED = "derived"
    NOT_APPLICABLE = "not_applicable"
    NOT_DISCLOSED = "not_disclosed"
    AMBIGUOUS = "ambiguous"
    PENDING_DEFINITION = "pending_definition"


class EvidenceRef(BaseModel):
    evidence_id: str
    document_name: str
    physical_page: int = Field(ge=1)
    locator: str
    exact_text: str


class FactInput(BaseModel):
    fact_id: str
    confirmed: bool


class FieldContract(BaseModel):
    field_id: str = Field(alias="id")
    export_name: str
    entity_grain: str
    value_type: str
    unit: str | None
    critical: bool
    pending_definition: bool = False


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
        if self.status is FactStatus.DISCLOSED and (self.value is None or not self.evidence):
            raise ValueError("disclosed facts require a value and evidence")
        if self.status is FactStatus.DERIVED:
            if self.value is None or not self.rule_version or not self.derived_inputs:
                raise ValueError("derived facts require a value, rule version, and inputs")
            if self.confirmed and not all(item.confirmed for item in self.derived_inputs):
                raise ValueError("confirmed derived facts require confirmed inputs")
        if self.status in {FactStatus.NOT_APPLICABLE, FactStatus.NOT_DISCLOSED} and self.value is not None:
            raise ValueError("not-applicable and not-disclosed facts must not carry a value")
        if self.field_id in _TRANCHE_FIELDS and not self.entity_key.startswith("security:"):
            raise ValueError("tranche facts require a security key")
        return self


_TRANCHE_FIELDS = {
    "security_code",
    "issue_rating",
    "bond_type_level_1",
    "bond_type_level_3",
    "maturity_date",
    "tranche_issue_amount",
    "tranche_current_balance",
    "tranche_level",
    "interest_payment_frequency",
    "first_interest_payment_date",
    "period_yield",
    "unit_remaining_face_value",
}


def load_field_contracts() -> dict[str, FieldContract]:
    path = Path(__file__).parents[2] / "config" / "fields.v1.json"
    fields = [FieldContract.model_validate(item) for item in json.loads(path.read_text())]
    return {field.field_id: field for field in fields}
