from npl_extract.review_page import render_review_page


def test_review_page_keeps_candidate_evidence_and_draft_export() -> None:
    page = render_review_page(
        [
            {
                "fact_id": "candidate:rating:1",
                "field_id": "issue_rating",
                "entity_key": "security:2689075",
                "status": "disclosed",
                "value": ["中债资信:AAAsf"],
                "effective_at": None,
                "evidence": [
                    {
                        "document_name": "发行说明书.pdf",
                        "physical_page": 2,
                        "locator": "评级表",
                        "evidence_id": "p002:b010",
                        "exact_text": "优先档 AAAsf",
                    }
                ],
            }
        ],
        {"issue_rating": "债项评级"},
    )

    assert "债项评级" in page
    assert "优先档 AAAsf" in page
    assert "导出复核草稿" in page
    assert "candidate:rating:1" in page


def test_review_page_marks_cashflow_evidence_incomplete_without_cell_evidence() -> None:
    page = render_review_page(
        [{"fact_id": "candidate:cashflow:1", "field_id": "cashflow_collection_table", "entity_key": "cashflow_row:test:2026-01", "status": "disclosed", "value": {"period": "2026-01"}, "effective_at": None, "evidence": []}],
        {"cashflow_collection_table": "现金流归集表"},
    )

    assert "现金流归集表的单元格证据不完整" in page
    assert "JSON.stringify(value)" in page
