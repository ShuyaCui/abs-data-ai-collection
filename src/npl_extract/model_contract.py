from __future__ import annotations

import json
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field, model_validator


_SHA256 = r"^[0-9a-f]{64}$"


def _digest(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ModelRequest(BaseModel):
    """Auditable call metadata; sensitive prompt text is deliberately absent."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    model_snapshot: str = Field(min_length=1)
    document_sha256: str = Field(pattern=_SHA256)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    prompt_hash: str = Field(pattern=_SHA256)
    authorization_id: str = Field(min_length=1)
    max_output_tokens: int = Field(ge=1)
    request_hash: str = ""

    @model_validator(mode="after")
    def bind_request_hash(self) -> ModelRequest:
        if len(set(self.evidence_ids)) != len(self.evidence_ids) or not all(self.evidence_ids):
            raise ValueError("evidence IDs must be unique and non-empty")
        expected = _digest(self.model_dump(exclude={"request_hash"}))
        if self.request_hash and self.request_hash != expected:
            raise ValueError("request hash does not match request metadata")
        object.__setattr__(self, "request_hash", expected)
        return self


class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_hash: str = Field(pattern=_SHA256)
    provider: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    model_snapshot: str = Field(min_length=1)
    response_hash: str = Field(pattern=_SHA256)
    candidate_fact_ids: tuple[str, ...] = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)


class ModelCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: ModelRequest
    response: ModelResponse

    @model_validator(mode="after")
    def bind_response(self) -> ModelCall:
        if self.response.request_hash != self.request.request_hash:
            raise ValueError("response must reference its request hash")
        if (self.response.provider, self.response.model_snapshot) != (self.request.provider, self.request.model_snapshot):
            raise ValueError("response provider and snapshot must match the request")
        return self
