from __future__ import annotations

from npl_extract.contracts import EvidenceRef, ExtractionFact, FactStatus
from npl_extract.extract import (
    RecoveryComponent,
    extract_issuance_result_ocr_facts,
    extract_prospectus_issue_amount_facts,
    extract_prospectus_market_facts,
    extract_prospectus_actual_financing_entity_facts,
    extract_prospectus_revolving_purchase_fact,
    extract_prospectus_issue_rating_facts,
    extract_prospectus_first_interest_payment_facts,
    extract_trustee_report_facts,
    derive_npl_recovery_cash,
)
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


def test_extracts_the_normalized_market_and_issuance_method_from_one_unique_prospectus_statement() -> None:
    pages = [
        PageContent(
            3,
            "",
            [
                Block(
                    "p003:b001",
                    3,
                    "本期资产支持证券拟采用公开簿记建档的方式在全国银行间债券市场发行。",
                    None,
                )
            ],
        )
    ]

    facts = extract_prospectus_market_facts(
        pages, "臻粹2026年第二期不良资产支持证券发行说明书.pdf", "product:臻粹2026-2", "pypdf-all"
    )

    assert {(fact.field_id, fact.value) for fact in facts} == {
        ("market", "银行间债券市场"),
        ("issuance_method", "簿记建档"),
    }
    assert all(fact.evidence[0].evidence_id == "p003:b001" for fact in facts)


def test_refuses_a_prospectus_block_that_repeats_the_issuance_route_statement() -> None:
    statement = "本期资产支持证券拟采用公开簿记建档的方式在全国银行间债券市场发行。"
    pages = [PageContent(3, "", [Block("p003:b001", 3, statement + statement, None)])]

    assert extract_prospectus_market_facts(pages, "臻粹不良资产支持证券发行说明书.pdf", "product:臻粹", "pypdf-all") == []


def test_extracts_a_static_pool_as_no_revolving_purchase_with_split_evidence() -> None:
    pages = [
        PageContent(
            90,
            "",
            [
                Block("p090:b005", 90, "本次交易中的“资产池”将是一个静态池，即信托财产交付日后，“受托人”将不会", None),
                Block("p090:b006", 90, "购买其他资产进入本次交易“资产池”或以其他资产替换已有资产。", None),
            ],
        )
    ]

    facts = extract_prospectus_revolving_purchase_fact(
        pages, "臻粹2026年第二期不良资产支持证券发行说明书.pdf", "product:臻粹2026-2", "pypdf-all"
    )

    assert len(facts) == 1
    assert facts[0].field_id == "has_revolving_purchase"
    assert facts[0].value is False
    assert [evidence.evidence_id for evidence in facts[0].evidence] == ["p090:b005", "p090:b006"]


def test_extracts_the_actual_financing_entity_only_from_the_sponsor_role_listing() -> None:
    pages = [
        PageContent(
            16,
            "",
            [
                Block("p016:b020", 16, "二、各参与机构名单", None),
                Block("p016:b021", 16, "（一）发起机构/贷款服务机构：广发银行股份有限公司（简称“广发", None),
                Block("p016:b022", 16, "银行”）", None),
            ],
        )
    ]

    facts = extract_prospectus_actual_financing_entity_facts(
        pages, "臻粹2026年第二期不良资产支持证券发行说明书.pdf", "product:臻粹2026-2", "pypdf-all"
    )

    assert len(facts) == 1
    assert facts[0].field_id == "actual_financing_entity"
    assert facts[0].value == ["广发银行股份有限公司"]
    assert [evidence.evidence_id for evidence in facts[0].evidence] == ["p016:b020", "p016:b021", "p016:b022"]


def test_refuses_a_cover_page_sponsor_role_without_the_participant_list_heading() -> None:
    pages = [
        PageContent(2, "", [Block("p002:b001", 2, "发起机构/贷款服务机构：广发银行股份有限公司（简称广发银行）", None)])
    ]

    assert extract_prospectus_actual_financing_entity_facts(pages, "臻粹不良资产支持证券发行说明书.pdf", "product:臻粹", "pypdf-all") == []


def test_refuses_two_complete_sponsor_listings_in_one_participant_list_block() -> None:
    pages = [
        PageContent(
            16,
            "",
            [
                Block("p016:b020", 16, "二、各参与机构名单", None),
                Block(
                    "p016:b021",
                    16,
                    "发起机构/贷款服务机构：甲银行股份有限公司（简称甲行） 发起机构/贷款服务机构：乙银行股份有限公司（简称乙行）",
                    None,
                ),
            ],
        )
    ]

    assert extract_prospectus_actual_financing_entity_facts(pages, "臻粹不良资产支持证券发行说明书.pdf", "product:臻粹", "pypdf-all") == []


def test_refuses_an_unclosed_sponsor_listing() -> None:
    pages = [
        PageContent(
            16,
            "",
            [
                Block("p016:b020", 16, "二、各参与机构名单", None),
                Block("p016:b021", 16, "发起机构/贷款服务机构：广发银行股份有限公司（简称广发银行", None),
            ],
        )
    ]

    assert extract_prospectus_actual_financing_entity_facts(pages, "臻粹不良资产支持证券发行说明书.pdf", "product:臻粹", "pypdf-all") == []


def test_refuses_a_valid_sponsor_listing_followed_by_an_unclosed_duplicate() -> None:
    pages = [
        PageContent(
            16,
            "",
            [
                Block("p016:b020", 16, "二、各参与机构名单", None),
                Block("p016:b021", 16, "发起机构/贷款服务机构：甲银行股份有限公司（简称甲行）发起机构/贷款服务机构：乙银行股份有限公司（简称乙行", None),
            ],
        )
    ]

    assert extract_prospectus_actual_financing_entity_facts(pages, "臻粹不良资产支持证券发行说明书.pdf", "product:臻粹", "pypdf-all") == []


def test_refuses_role_prose_mixed_into_the_sponsor_name() -> None:
    pages = [
        PageContent(
            16,
            "",
            [
                Block("p016:b020", 16, "二、各参与机构名单", None),
                Block("p016:b021", 16, "发起机构/贷款服务机构：受托机构为乙信托有限公司（简称乙信托）", None),
            ],
        )
    ]

    assert extract_prospectus_actual_financing_entity_facts(pages, "臻粹不良资产支持证券发行说明书.pdf", "product:臻粹", "pypdf-all") == []


def test_refuses_multiple_companies_in_one_sponsor_role_listing() -> None:
    pages = [
        PageContent(
            16,
            "",
            [
                Block("p016:b020", 16, "二、各参与机构名单", None),
                Block("p016:b021", 16, "发起机构/贷款服务机构：甲银行股份有限公司、乙银行股份有限公司（简称甲乙）", None),
            ],
        )
    ]

    assert extract_prospectus_actual_financing_entity_facts(pages, "臻粹不良资产支持证券发行说明书.pdf", "product:臻粹", "pypdf-all") == []


def test_refuses_static_pool_text_repeated_inside_one_evidence_pair() -> None:
    pages = [
        PageContent(
            90,
            "",
            [
                Block("p090:b005", 90, "资产池将是一个静态池，受托人将不会。资产池将是一个静态池，受托人将不会。", None),
                Block("p090:b006", 90, "购买其他资产或以其他资产替换已有资产。购买其他资产或以其他资产替换已有资产。", None),
            ],
        )
    ]

    assert extract_prospectus_revolving_purchase_fact(pages, "臻粹不良资产支持证券发行说明书.pdf", "product:臻粹", "pypdf-all") == []


def test_refuses_a_complete_static_pool_statement_in_one_block_without_a_linked_second_block() -> None:
    pages = [
        PageContent(
            90,
            "",
            [
                Block("p090:b005", 90, "资产池将是一个静态池，受托人将不会购买其他资产或以其他资产替换已有资产。", None),
                Block("p090:b006", 90, "这是不相关的后续段落。", None),
            ],
        )
    ]

    assert extract_prospectus_revolving_purchase_fact(pages, "臻粹不良资产支持证券发行说明书.pdf", "product:臻粹", "pypdf-all") == []


def test_extracts_only_unique_product_level_issue_amount_rows_from_the_prospectus() -> None:
    pages = [
        PageContent(
            2,
            "",
            [
                Block("p002:b001", 2, "证券名称 发行金额（万元）规模占比 还本方式", None),
                Block("p002:b002", 2, "优先档 13,200.00 72.53% 过手 固定利率", None),
                Block("p002:b003", 2, "次级档 5,000.00 27.47% 过手 无票面利率", None),
                Block("p002:b004", 2, "总计 18,200.00 100.00% -", None),
            ],
        )
    ]

    facts = extract_prospectus_issue_amount_facts(
        pages, "臻粹2026年第二期不良资产支持证券发行说明书.pdf", "product:臻粹2026-2", "pypdf-all"
    )

    assert {(fact.field_id, fact.value) for fact in facts} == {
        ("issue_amount_senior", "1.32"),
        ("issue_amount_mezzanine", None),
        ("issue_amount_subordinated", "0.5"),
    }
    mezzanine = next(fact for fact in facts if fact.field_id == "issue_amount_mezzanine")
    assert mezzanine.status is FactStatus.NOT_APPLICABLE
    assert mezzanine.evidence[-1].evidence_id == "p002:b004"
    assert all([evidence.evidence_id for evidence in fact.evidence] == ["p002:b001", fact.evidence[-1].evidence_id] for fact in facts if fact.status is FactStatus.DISCLOSED)


def test_refuses_equivalent_mezzanine_labels_with_conflicting_amounts() -> None:
    pages = [
        PageContent(
            2,
            "",
            [
                Block("p002:b001", 2, "证券名称 发行金额（万元）规模占比", None),
                Block("p002:b002", 2, "次优档 100.00 1.00% 过手", None),
                Block("p002:b003", 2, "次优级 200.00 2.00% 过手", None),
                Block("p002:b004", 2, "总计 300.00 3.00% -", None),
            ],
        )
    ]

    assert extract_prospectus_issue_amount_facts(pages, "臻粹不良资产支持证券发行说明书.pdf", "product:臻粹", "pypdf-all") == []


def test_refuses_a_duplicate_issue_amount_row_later_in_the_same_table() -> None:
    pages = [
        PageContent(
            2,
            "",
            [
                Block("p002:b001", 2, "证券名称 发行金额（万元）规模占比", None),
                Block("p002:b002", 2, "优先档 100.00 1.00% 过手", None),
                Block("p002:b003", 2, "说明一", None),
                Block("p002:b004", 2, "说明二", None),
                Block("p002:b005", 2, "说明三", None),
                Block("p002:b006", 2, "说明四", None),
                Block("p002:b007", 2, "优先档 200.00 2.00% 过手", None),
                Block("p002:b008", 2, "总计 300.00 3.00% -", None),
            ],
        )
    ]

    assert extract_prospectus_issue_amount_facts(pages, "臻粹不良资产支持证券发行说明书.pdf", "product:臻粹", "pypdf-all") == []


def test_does_not_assert_mezzanine_not_applicable_when_an_extra_tier_row_exists() -> None:
    pages = [
        PageContent(
            2,
            "",
            [
                Block("p002:b001", 2, "证券名称 发行金额（万元）规模占比", None),
                Block("p002:b002", 2, "优先档 100.00 40.00% 过手", None),
                Block("p002:b003", 2, "劣后档资产支持证券 50.00 20.00% 过手", None),
                Block("p002:b004", 2, "次级档 100.00 40.00% 过手", None),
                Block("p002:b005", 2, "总计 250.00 100.00% -", None),
            ],
        )
    ]

    facts = extract_prospectus_issue_amount_facts(pages, "臻粹不良资产支持证券发行说明书.pdf", "product:臻粹", "pypdf-all")

    assert "issue_amount_mezzanine" not in {fact.field_id for fact in facts}


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


def test_projects_a_prospectus_first_payment_date_to_explicit_tranche_associations() -> None:
    associations = [
        ExtractionFact(
            fact_id="senior-level",
            field_id="tranche_level",
            entity_key="security:2689075",
            status=FactStatus.DISCLOSED,
            value="优先档",
            evidence=[
                EvidenceRef(
                    evidence_id="p001:b005",
                    artifact_scope="docling-ocr-all",
                    document_name="臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf",
                    physical_page=1,
                    locator="证券名称",
                    exact_text="优先档",
                )
            ],
        ),
        ExtractionFact(
            fact_id="subordinated-level",
            field_id="tranche_level",
            entity_key="security:2689076",
            status=FactStatus.DISCLOSED,
            value="次级档",
            evidence=[
                EvidenceRef(
                    evidence_id="p002:b003",
                    artifact_scope="docling-ocr-all",
                    document_name="臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf",
                    physical_page=2,
                    locator="证券名称",
                    exact_text="次级档",
                )
            ],
        ),
    ]
    pages = [
        PageContent(
            2,
            "",
            [Block("p002:b028", 2, "资产支持证券的第一个支付日是 2026 年 5 月 23 日", None)],
        )
    ]

    facts = extract_prospectus_first_interest_payment_facts(
        pages,
        "臻粹2026年第二期不良资产支持证券发行说明书.pdf",
        associations,
        "pypdf-pages-2-2",
    )

    assert {(fact.entity_key, fact.value) for fact in facts} == {
        ("security:2689075", "2026-05-23"),
        ("security:2689076", "2026-05-23"),
    }
    assert all(fact.field_id == "first_interest_payment_date" for fact in facts)
    assert all({item.document_name for item in fact.evidence} == {"臻粹2026年第二期不良资产支持证券发行说明书.pdf", "臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf"} for fact in facts)


def test_refuses_cross_product_or_ambiguous_tranche_associations() -> None:
    pages = [PageContent(2, "", [Block("p002:b028", 2, "资产支持证券的第一个支付日是 2026 年 5 月 23 日", None)])]
    association = ExtractionFact(
        fact_id="wrong-product-level",
        field_id="tranche_level",
        entity_key="security:2689075",
        status=FactStatus.DISCLOSED,
        value="优先档",
        evidence=[
            EvidenceRef(
                evidence_id="p001:b005",
                artifact_scope="docling-ocr-all",
                document_name="另一产品簿记建档发行结果公告.pdf",
                physical_page=1,
                locator="证券名称",
                exact_text="优先档",
            )
        ],
    )

    assert (
        extract_prospectus_first_interest_payment_facts(
            pages, "臻粹2026年第二期不良资产支持证券发行说明书.pdf", [association], "pypdf-pages-2-2"
        )
        == []
    )


def test_refuses_two_tranche_levels_for_one_security() -> None:
    pages = [PageContent(2, "", [Block("p002:b028", 2, "资产支持证券的第一个支付日是 2026 年 5 月 23 日", None)])]
    associations = [
        ExtractionFact(
            fact_id=f"level-{level}",
            field_id="tranche_level",
            entity_key="security:2689075",
            status=FactStatus.DISCLOSED,
            value=level,
            evidence=[
                EvidenceRef(
                    evidence_id=f"p001:{index}",
                    artifact_scope="docling-ocr-all",
                    document_name="臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf",
                    physical_page=1,
                    locator="证券名称",
                    exact_text=level,
                )
            ],
        )
        for index, level in enumerate(("优先档", "次级档"), start=1)
    ]

    assert (
        extract_prospectus_first_interest_payment_facts(
            pages, "臻粹2026年第二期不良资产支持证券发行说明书.pdf", associations, "pypdf-pages-2-2"
        )
        == []
    )


def test_projects_prospectus_issue_ratings_to_unique_tranche_associations() -> None:
    associations = [
        ExtractionFact(
            fact_id=f"level-{level}",
            field_id="tranche_level",
            entity_key=entity_key,
            status=FactStatus.DISCLOSED,
            value=level,
            evidence=[
                EvidenceRef(
                    evidence_id=f"p001:{index}",
                    artifact_scope="docling-ocr-all",
                    document_name="臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf",
                    physical_page=index,
                    locator="证券名称",
                    exact_text=level,
                )
            ],
        )
        for index, (level, entity_key) in enumerate(
            (("优先档", "security:2689075"), ("次级档", "security:2689076")), start=1
        )
    ]
    pages = [
        PageContent(
            2,
            "",
            [
                Block("p002:b011", 2, "方式 利率类型 预期到期日 法定到期日 评级", None),
                Block("p002:b012", 2, "（中债资信/中诚信）", None),
                Block("p002:b013", 2, "优先档 13,200.00 72.53% 过手 固定利率 2028/2/23 2032/4/23 AAAsf/AAAsf", None),
                Block("p002:b014", 2, "次级档 5,000.00 27.47% 过手 无票面利率 2029/4/23 2032/4/23 无评级", None),
            ],
        )
    ]

    facts = extract_prospectus_issue_rating_facts(
        pages,
        "臻粹2026年第二期不良资产支持证券发行说明书.pdf",
        associations,
        "pypdf-pages-2-2",
    )

    assert {(fact.entity_key, tuple(fact.value)) for fact in facts} == {
        ("security:2689075", ("中债资信:AAAsf", "中诚信国际:AAAsf")),
        ("security:2689076", ("中债资信:无评级", "中诚信国际:无评级")),
    }
    assert all(fact.field_id == "issue_rating" for fact in facts)
    assert all(fact.evidence[0].locator == "发行要素/评级（中债资信/中诚信）" for fact in facts)


def test_refuses_a_single_rating_under_a_two_agency_prospectus_header() -> None:
    association = ExtractionFact(
        fact_id="senior-level",
        field_id="tranche_level",
        entity_key="security:2689075",
        status=FactStatus.DISCLOSED,
        value="优先档",
        evidence=[
            EvidenceRef(
                evidence_id="p001:b005",
                artifact_scope="docling-ocr-all",
                document_name="臻粹2026年第二期不良资产支持证券簿记建档发行结果公告.pdf",
                physical_page=1,
                locator="证券名称",
                exact_text="优先档",
            )
        ],
    )
    pages = [
        PageContent(
            2,
            "",
            [
                Block("p002:b011", 2, "方式 利率类型 预期到期日 法定到期日 评级", None),
                Block("p002:b012", 2, "（中债资信/中诚信）", None),
                Block("p002:b013", 2, "优先档 13,200.00 72.53% 过手 固定利率 2028/2/23 2032/4/23 AAAsf", None),
            ],
        )
    ]

    assert (
        extract_prospectus_issue_rating_facts(
            pages, "臻粹2026年第二期不良资产支持证券发行说明书.pdf", [association], "pypdf-pages-2-2"
        )
        == []
    )


def test_extracts_post_payment_tranche_balances_with_effective_date() -> None:
    pages = [
        PageContent(1, "", [Block("p001:b012", 1, "报告日期：2026 年 8 月 17 日", None)]),
        PageContent(5, "", [Block("p005:b010", 5, "本期支付日 2026 年8 月24 日", None)]),
        PageContent(
            6,
            "",
            [
                Block("p006:b004", 6, "（二）资产支持证券本息兑付情况：", None),
                Block("p006:b006", 6, "证券代码 2689075 2689076", None),
                Block("p006:b013", 6, "本息兑付后剩余本金值 83,978,400.00 50,000,000.00", None),
            ],
        ),
    ]

    facts = extract_trustee_report_facts(pages, "第4期受托机构报告.pdf", "report:2026-08-17", "pypdf-pages-1-6")

    balances = [fact for fact in facts if fact.field_id == "tranche_current_balance"]
    assert {(fact.entity_key, fact.value) for fact in balances} == {
        ("security:2689075", "0.839784"),
        ("security:2689076", "0.5"),
    }
    assert {fact.effective_at.isoformat() for fact in balances} == {"2026-08-24"}
    assert all({item.evidence_id for item in fact.evidence} >= {"p001:b012", "p005:b010", "p006:b006", "p006:b013"} for fact in balances)


def test_refuses_balances_when_a_second_payout_section_is_incomplete() -> None:
    pages = [
        PageContent(1, "", [Block("p001:b012", 1, "报告日期：2026 年 8 月 17 日", None)]),
        PageContent(5, "", [Block("p005:b010", 5, "本期支付日 2026 年8 月24 日", None)]),
        PageContent(
            6,
            "",
            [
                Block("p006:b004", 6, "（二）资产支持证券本息兑付情况：", None),
                Block("p006:b006", 6, "证券代码 2689075 2689076", None),
                Block("p006:b013", 6, "本息兑付后剩余本金值 83,978,400.00 50,000,000.00", None),
            ],
        ),
        PageContent(7, "", [Block("p007:b004", 7, "（二）资产支持证券本息兑付情况：", None)]),
    ]

    facts = extract_trustee_report_facts(pages, "第4期受托机构报告.pdf", "report:2026-08-17", "pypdf-pages-1-7")

    assert not [fact for fact in facts if fact.field_id == "tranche_current_balance"]


def test_refuses_balances_when_the_two_codes_are_not_distinct() -> None:
    pages = [
        PageContent(1, "", [Block("p001:b012", 1, "报告日期：2026 年 8 月 17 日", None)]),
        PageContent(5, "", [Block("p005:b010", 5, "本期支付日 2026 年8 月24 日", None)]),
        PageContent(
            6,
            "",
            [
                Block("p006:b004", 6, "（二）资产支持证券本息兑付情况：", None),
                Block("p006:b006", 6, "证券代码 2689075 2689075", None),
                Block("p006:b013", 6, "本息兑付后剩余本金值 83,978,400.00 50,000,000.00", None),
            ],
        ),
    ]

    facts = extract_trustee_report_facts(pages, "第4期受托机构报告.pdf", "report:2026-08-17", "pypdf-pages-1-6")

    assert not [fact for fact in facts if fact.field_id == "tranche_current_balance"]
