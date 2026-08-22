from __future__ import annotations

import pytest

from npl_extract.model_contract import ModelCall, ModelRequest, ModelResponse


def test_model_call_binds_a_minimum_fragment_request_to_its_audit_response() -> None:
    request = ModelRequest(
        provider="qwen",
        model_snapshot="qwen3.7-plus@2026-08-22",
        document_sha256="a" * 64,
        evidence_ids=["p003:b012"],
        prompt_hash="b" * 64,
        authorization_id="security-approval-001",
        max_output_tokens=512,
    )

    call = ModelCall(
        request=request,
        response=ModelResponse(
            request_hash=request.request_hash,
            provider="qwen",
            model_snapshot="qwen3.7-plus@2026-08-22",
            response_hash="c" * 64,
            candidate_fact_ids=["fact:issuance:001"],
            input_tokens=123,
            output_tokens=45,
            latency_ms=678,
        ),
    )

    assert call.request.request_hash
    assert "prompt" not in call.model_dump()["request"]

    with pytest.raises(Exception, match="frozen"):
        call.request.provider = "deepseek"
    with pytest.raises(AttributeError):
        call.request.evidence_ids.append("p003:b013")
    with pytest.raises(AttributeError):
        call.response.candidate_fact_ids.append("fact:issuance:002")
