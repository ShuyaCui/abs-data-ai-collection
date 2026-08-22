from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from npl_extract.contracts import (
    EvidenceRef,
    ExtractionFact,
    FactInput,
    FactStatus,
    load_field_contracts,
)


def evidence() -> EvidenceRef:
    return EvidenceRef(
        evidence_id="sha256:p001:b001",
        artifact_scope="pypdf-all",
        document_name="发行说明书.pdf",
        physical_page=1,
        locator="第一段",
        exact_text="2026-08-17",
    )


def test_loads_all_42_versioned_field_contracts() -> None:
    contracts = load_field_contracts()

    assert len(contracts) == 42
    assert contracts["npl_trustee_recovery_cash"].export_name == "NPL-受托已回收（亿）"
    assert contracts["bond_type_level_1"].pending_definition
    assert contracts["security_code"].contract_version == "v1"
    assert FactStatus.DERIVED not in contracts["security_code"].allowed_statuses
    assert FactStatus.DERIVED in contracts["npl_trustee_recovery_cash"].allowed_statuses
    assert contracts["latest_report_date"].source_precedence


def test_rejects_unknown_fields_and_disallowed_statuses() -> None:
    with pytest.raises(ValidationError, match="unknown field"):
        ExtractionFact(fact_id="unknown", field_id="not-a-field", entity_key="product:test", status=FactStatus.NOT_DISCLOSED)
    with pytest.raises(ValidationError, match="does not allow"):
        ExtractionFact(
            fact_id="wrong-status",
            field_id="security_code",
            entity_key="security:123",
            status=FactStatus.DERIVED,
            value="123",
            evidence=[evidence()],
            rule_version="test-v1",
            derived_inputs=[FactInput(fact_id="input", confirmed=True)],
        )


def test_rejects_disclosed_value_without_evidence() -> None:
    with pytest.raises(ValidationError, match="evidence"):
        ExtractionFact(
            fact_id="f1",
            field_id="security_code",
            entity_key="security:123",
            status=FactStatus.DISCLOSED,
            value="123",
        )


def test_rejects_derived_value_without_confirmed_inputs() -> None:
    with pytest.raises(ValidationError, match="derived"):
        ExtractionFact(
            fact_id="f2",
            field_id="npl_trustee_recovery_cash",
            entity_key="report:test",
            status=FactStatus.DERIVED,
            value="0.6040795674",
            evidence=[evidence()],
            rule_version="recovery-cash-v1",
            derived_inputs=[],
        )


def test_rejects_confirmed_derived_value_with_provisional_input() -> None:
    with pytest.raises(ValidationError, match="confirmed"):
        ExtractionFact(
            fact_id="f3",
            field_id="npl_trustee_recovery_cash",
            entity_key="product:test",
            status=FactStatus.DERIVED,
            value="0.6040795674",
            evidence=[evidence()],
            rule_version="recovery-cash-v1",
            confirmed=True,
            derived_inputs=[FactInput(fact_id="input", confirmed=False)],
        )


def test_rejects_tranche_fact_without_security_key() -> None:
    with pytest.raises(ValidationError, match="security key"):
        ExtractionFact(
            fact_id="f4",
            field_id="tranche_issue_amount",
            entity_key="product:test",
            status=FactStatus.DISCLOSED,
            value="1.0",
            evidence=[evidence()],
            effective_at=date(2026, 1, 1),
        )


def test_preserves_a_contractual_string_array_value() -> None:
    fact = ExtractionFact(
        fact_id="rating-array",
        field_id="issue_rating",
        entity_key="security:123",
        status=FactStatus.DISCLOSED,
        value=["中债资信:AAAsf", "中诚信国际:AAAsf"],
        evidence=[evidence()],
    )

    assert fact.value == ["中债资信:AAAsf", "中诚信国际:AAAsf"]


def test_preserves_a_contractual_boolean_value_without_coercing_it_to_text() -> None:
    fact = ExtractionFact(
        fact_id="static-pool",
        field_id="has_revolving_purchase",
        entity_key="product:test",
        status=FactStatus.DISCLOSED,
        value=False,
        evidence=[evidence()],
    )

    assert fact.value is False
    with pytest.raises(ValidationError, match="boolean facts require a boolean"):
        ExtractionFact(
            fact_id="wrong-static-pool",
            field_id="has_revolving_purchase",
            entity_key="product:test",
            status=FactStatus.DISCLOSED,
            value="false",
            evidence=[evidence()],
        )
    with pytest.raises(ValidationError):
        ExtractionFact(
            fact_id="numeric-static-pool",
            field_id="has_revolving_purchase",
            entity_key="product:test",
            status=FactStatus.DISCLOSED,
            value=0,
            evidence=[evidence()],
        )


@pytest.mark.parametrize(
    ("field_id", "entity_key", "message"),
    [
        ("asset_full_name", "security:123", "product key"),
        ("latest_report_date", "product:test", "report key"),
        ("cashflow_collection_table", "product:test", "cashflow_row key"),
    ],
)
def test_rejects_entity_key_with_the_wrong_contract_grain(field_id: str, entity_key: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        ExtractionFact(fact_id="wrong-grain", field_id=field_id, entity_key=entity_key, status=FactStatus.NOT_DISCLOSED)
