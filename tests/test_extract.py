from __future__ import annotations

from npl_extract.contracts import EvidenceRef, FactStatus
from npl_extract.extract import RecoveryComponent, derive_npl_recovery_cash


def component(fact_id: str, amount: str, row: str) -> RecoveryComponent:
    return RecoveryComponent(
        fact_id=fact_id,
        amount_cny=amount,
        evidence=EvidenceRef(
            evidence_id=f"sha256:p007:{fact_id}",
            document_name="受托机构报告2026年度第4期总第4期.pdf",
            physical_page=7,
            locator=f"四、资产池表现情况（三）资金池现金流流入/{row}/累计回收金额",
            exact_text=amount,
        ),
    )


def test_derives_npl_recovery_from_disposal_rows_only() -> None:
    result = derive_npl_recovery_cash(
        entity_key="product:臻粹2026-2",
        in_progress=component("in-progress", "30466642.99", "处置中"),
        completed=component("completed", "29941313.75", "本期处置完毕"),
    )

    assert result.status is FactStatus.DERIVED
    assert result.value == "0.6040795674"
    assert [item.fact_id for item in result.derived_inputs] == ["in-progress", "completed"]
    assert all("其他收入" not in evidence.locator for evidence in result.evidence)
