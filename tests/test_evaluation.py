from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

from npl_extract.contracts import EvidenceRef, ExtractionFact, FactStatus, load_field_contracts
from npl_extract.evaluation import GoldFact, GoldSplit, evaluate_case, validate_gold_splits


def _evidence(evidence_id: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        artifact_scope="pypdf-all",
        document_name="发行公告.pdf",
        physical_page=1,
        locator="公告标题",
        exact_text="臻粹不良资产支持证券发行公告",
    )


def test_evaluates_exact_fact_evidence_and_false_fill_metrics() -> None:
    gold = [
        GoldFact(
            case_id="dev-001",
            product_key="product:sample-a",
            split=GoldSplit.DEVELOPMENT,
            field_id="security_code",
            entity_key="security:2689075",
            status=FactStatus.DISCLOSED,
            value="2689075",
            effective_at=None,
            evidence_ids=["p001:b001"],
        ),
        GoldFact(
            case_id="dev-001",
            product_key="product:sample-a",
            split=GoldSplit.DEVELOPMENT,
            field_id="initial_cutoff_date",
            entity_key="product:sample-a",
            status=FactStatus.NOT_DISCLOSED,
            value=None,
            effective_at=None,
            evidence_ids=[],
        ),
    ]
    candidates = [
        ExtractionFact(
            fact_id="code",
            field_id="security_code",
            entity_key="security:2689075",
            status=FactStatus.DISCLOSED,
            value="2689075",
            evidence=[_evidence("p001:b001")],
        ),
        ExtractionFact(
            fact_id="cutoff",
            field_id="initial_cutoff_date",
            entity_key="product:sample-a",
            status=FactStatus.DISCLOSED,
            value="2026-01-26",
            effective_at=date(2026, 1, 26),
            evidence=[_evidence("p001:b002")],
        ),
    ]

    result = evaluate_case(gold, candidates)

    assert result.total == 2
    assert result.exact_fact_matches == 1
    assert result.exact_evidence_matches == 1
    assert result.false_fills == 1
    assert result.critical_failures == 1


def test_rejects_a_product_present_in_more_than_one_gold_split() -> None:
    record = dict(
        case_id="case",
        product_key="product:sample-a",
        field_id="asset_full_name",
        entity_key="product:sample-a",
        status=FactStatus.NOT_DISCLOSED,
        value=None,
        effective_at=None,
        evidence_ids=[],
    )

    with pytest.raises(ValueError, match="more than one split"):
        validate_gold_splits(
            [
                GoldFact(split=GoldSplit.DEVELOPMENT, **record),
                GoldFact(split=GoldSplit.HOLDOUT, **record),
            ]
        )


def test_gold_contract_rejects_undeclared_fields() -> None:
    with pytest.raises(ValueError, match="extra"):
        GoldFact(
            case_id="case",
            product_key="product:sample-a",
            split=GoldSplit.DEVELOPMENT,
            field_id="asset_full_name",
            entity_key="product:sample-a",
            status=FactStatus.NOT_DISCLOSED,
            value=None,
            effective_at=None,
            evidence_ids=[],
            unapproved="value",
        )


def test_gold_contract_rejects_unknown_field_ids() -> None:
    with pytest.raises(ValueError, match="unknown field"):
        GoldFact(
            case_id="case",
            product_key="product:sample-a",
            split=GoldSplit.DEVELOPMENT,
            field_id="not-a-field",
            entity_key="product:sample-a",
            status=FactStatus.NOT_DISCLOSED,
            value=None,
            effective_at=None,
            evidence_ids=[],
        )


def test_gold_contract_requires_evidence_and_candidate_fact_shape() -> None:
    with pytest.raises(ValueError, match="evidence"):
        GoldFact(
            case_id="case",
            product_key="product:sample-a",
            split=GoldSplit.DEVELOPMENT,
            field_id="asset_full_name",
            entity_key="product:sample-a",
            status=FactStatus.DISCLOSED,
            value="臻粹不良资产支持证券",
            effective_at=None,
            evidence_ids=[],
        )

    with pytest.raises(ValueError, match="product key"):
        GoldFact(
            case_id="case",
            product_key="product:sample-a",
            split=GoldSplit.DEVELOPMENT,
            field_id="asset_full_name",
            entity_key="security:2689075",
            status=FactStatus.DISCLOSED,
            value="臻粹不良资产支持证券",
            effective_at=None,
            evidence_ids=["p001:b001"],
        )


def test_counts_an_unexpected_disclosed_candidate_as_a_critical_false_fill() -> None:
    gold = [
        GoldFact(
            case_id="dev-001",
            product_key="product:sample-a",
            split=GoldSplit.DEVELOPMENT,
            field_id="security_code",
            entity_key="security:2689075",
            status=FactStatus.DISCLOSED,
            value="2689075",
            effective_at=None,
            evidence_ids=["p001:b001"],
        )
    ]
    candidates = [
        ExtractionFact(
            fact_id="code-a",
            field_id="security_code",
            entity_key="security:2689075",
            status=FactStatus.DISCLOSED,
            value="2689075",
            evidence=[_evidence("p001:b001")],
        ),
        ExtractionFact(
            fact_id="code-b",
            field_id="security_code",
            entity_key="security:2689076",
            status=FactStatus.DISCLOSED,
            value="2689076",
            evidence=[_evidence("p001:b002")],
        ),
    ]

    result = evaluate_case(gold, candidates)

    assert result.false_fills == 1
    assert result.critical_failures == 1


def test_gold_json_schema_stays_aligned_with_field_contracts() -> None:
    schema = json.loads((Path(__file__).parents[1] / "evaluation" / "gold.schema.json").read_text())

    assert set(schema["properties"]["field_id"]["enum"]) == set(load_field_contracts())
