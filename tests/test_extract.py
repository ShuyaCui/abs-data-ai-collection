from __future__ import annotations

from npl_extract.contracts import EvidenceRef, FactStatus
from npl_extract.extract import RecoveryComponent, extract_issuance_result_ocr_facts, extract_trustee_report_facts, derive_npl_recovery_cash
from npl_extract.parsers import Block, PageContent


def component(fact_id: str, amount: str, row: str) -> RecoveryComponent:
    return RecoveryComponent(
        fact_id=fact_id,
        amount_cny=amount,
        evidence=EvidenceRef(
            evidence_id=f"sha256:p007:{fact_id}",
            artifact_scope="pypdf-all",
            document_name="受托机构报告2026年度第4期总第4期.pdf",
            physical_page=7,
            locator=f"四、资产池表现情况（三）资金池现金流流入/{row}/累计回收金额",
            exact_text=amount,
        ),
    )


def test_derives_npl_recovery_from_disposal_rows_only() -> None:
    result = derive_npl_recovery_cash(
        entity_key="report:臻粹2026-2",
        in_progress=component("in-progress", "30466642.99", "处置中"),
        completed=component("completed", "29941313.75", "本期处置完毕"),
    )

    assert result.status is FactStatus.DERIVED
    assert result.value == "0.6040795674"
    assert [item.fact_id for item in result.derived_inputs] == ["in-progress", "completed"]
    assert all("其他收入" not in evidence.locator for evidence in result.evidence)


def test_extracts_trustee_report_date_and_recovery_with_evidence() -> None:
    pages = [
        PageContent(1, "", [Block("p001:b001", 1, "受托机构报告", None), Block("p001:b012", 1, "报告日期：2026 年 8 月 17 日", None)]),
        PageContent(
            7,
            "",
            [
                Block("p007:b027", 7, "（三）资金池现金流流入", None),
                Block("p007:b028", 7, "处置中 6,339,491.27 30,466,642.99 不适用 不适用", None),
                Block("p007:b029", 7, "本期处置完毕 1,155,311.30 29,941,313.75 不适用 96.76%", None),
                Block("p007:b030", 7, "2-其他现金流流入 本期回收金额 5,180.97", None),
            ],
        ),
    ]

    facts = extract_trustee_report_facts(pages, "第4期受托报告.pdf", "report:2026-08-17", "pypdf-all")

    assert facts[0].field_id == "latest_report_date"
    assert facts[0].value == "2026-08-17"
    assert facts[0].evidence[0].evidence_id == "p001:b012"
    assert facts[0].evidence[0].artifact_scope == "pypdf-all"
    assert [fact.field_id for fact in facts[1:]] == [
        "npl_recovery_in_progress_cumulative",
        "npl_recovery_completed_cumulative",
        "npl_trustee_recovery_cash",
    ]
    assert facts[3].value == "0.6040795674"
    assert {item.evidence_id for item in facts[3].evidence} == {"p007:b028", "p007:b029"}


def test_refuses_a_non_trustee_document_and_invalid_date() -> None:
    pages = [PageContent(1, "", [Block("p001:b001", 1, "报告日期：2026 年 2 月 30 日", None)])]

    assert extract_trustee_report_facts(pages, "发行说明书.pdf", "report:test", "pypdf-all") == []
    assert extract_trustee_report_facts(pages, "受托机构报告.pdf", "report:test", "pypdf-all") == []


def test_extracts_each_securitys_disclosed_tranche_level_from_the_ocr_result_table() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "臻粹2026年第二期不良资产支持证券簿记建档发行结果公告", [0, 0, 1, 1]),
                Block("p001:b002", 1, "证券名称", [0, 0, 1, 1]),
                Block("p001:b003", 1, "资产支持证券优先档资产支持证券", [0, 0, 1, 1]),
                Block("p001:b004", 1, "证券代码", [0, 0, 1, 1]),
                Block("p001:b005", 1, "2689075", [0, 0, 1, 1]),
                Block("p001:b006", 1, "预期到期日", [0, 0, 1, 1]),
                Block("p001:b007", 1, "2028年2月23日", [0, 0, 1, 1]),
                Block("p001:b008", 1, "实际发行总额", [0, 0, 1, 1]),
                Block("p001:b009", 1, "13,200.00万元", [0, 0, 1, 1]),
            ],
            ocr_requested=True,
        ),
        PageContent(
            2,
            "",
            [
                Block("p002:b001", 2, "证券名称", [0, 0, 1, 1]),
                Block("p002:b002", 2, "资产支持证券次级档资产支持证券", [0, 0, 1, 1]),
                Block("p002:b003", 2, "证券代码", [0, 0, 1, 1]),
                Block("p002:b004", 2, "2689076", [0, 0, 1, 1]),
                Block("p002:b005", 2, "预期到期日", [0, 0, 1, 1]),
                Block("p002:b006", 2, "2029年4月23日", [0, 0, 1, 1]),
                Block("p002:b007", 2, "实际发行总额", [0, 0, 1, 1]),
                Block("p002:b008", 2, "5,000.00万元", [0, 0, 1, 1]),
            ],
            ocr_requested=True,
        ),
    ]

    facts = extract_issuance_result_ocr_facts(
        pages, "臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf", "docling-ocr-all"
    )

    levels = {(fact.entity_key, fact.value) for fact in facts if fact.field_id == "tranche_level"}
    assert levels == {("security:2689075", "优先档"), ("security:2689076", "次级档")}
    assert all(fact.evidence[-1].locator == "簿记建档结果公告/证券信息表/证券名称" for fact in facts if fact.field_id == "tranche_level")


def test_refuses_a_security_level_from_an_unrelated_ocr_name_block() -> None:
    pages = [
        PageContent(
            1,
            "",
            [
                Block("p001:b001", 1, "臻粹2026年第二期不良资产支持证券簿记建档发行结果公告", [0, 0, 1, 1]),
                Block("p001:b002", 1, "证券名称", [0, 0, 1, 1]),
                Block("p001:b003", 1, "优先档说明", [0, 0, 1, 1]),
                Block("p001:b004", 1, "正文一", [0, 0, 1, 1]),
                Block("p001:b005", 1, "正文二", [0, 0, 1, 1]),
                Block("p001:b006", 1, "正文三", [0, 0, 1, 1]),
                Block("p001:b007", 1, "正文四", [0, 0, 1, 1]),
                Block("p001:b008", 1, "正文五", [0, 0, 1, 1]),
                Block("p001:b009", 1, "正文六", [0, 0, 1, 1]),
                Block("p001:b010", 1, "证券代码", [0, 0, 1, 1]),
                Block("p001:b011", 1, "2689075", [0, 0, 1, 1]),
                Block("p001:b012", 1, "预期到期日", [0, 0, 1, 1]),
                Block("p001:b013", 1, "2028年2月23日", [0, 0, 1, 1]),
                Block("p001:b014", 1, "实际发行总额", [0, 0, 1, 1]),
                Block("p001:b015", 1, "13,200.00万元", [0, 0, 1, 1]),
            ],
            ocr_requested=True,
        )
    ]

    facts = extract_issuance_result_ocr_facts(
        pages, "臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf", "docling-ocr-all"
    )

    assert {fact.field_id for fact in facts} == {"security_code", "maturity_date", "tranche_issue_amount"}
