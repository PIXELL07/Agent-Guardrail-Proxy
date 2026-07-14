"""
Request/response models for the guardrail proxy.

The core idea: an agent is about to call a tool (e.g. send_email, run_sql,
create_invoice). Before that call actually executes, it gets routed through
this proxy's /v1/inspect endpoint. We inspect the *arguments* being passed
to the tool (which often contain text pulled from untrusted sources, like a
scraped webpage or a user-uploaded document) for injected instructions.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

# Limits chosen to comfortably fit real tool-call arguments (which are
# typically short strings/numbers) while blocking a payload designed to
# exhaust CPU/memory in the detection tiers -- TF-IDF vectorization and
# regex scanning both scale with input size, so an unbounded payload is a
# real DoS vector, not just a theoretical one.
MAX_ARGUMENT_FIELDS = 50
MAX_FIELD_VALUE_LENGTH = 20_000
MAX_SOURCE_CONTEXT_LENGTH = 100_000


class ToolCallPayload(BaseModel):
    """What the agent is about to send to a tool."""

    agent_id: str = Field(..., min_length=1, max_length=200)
    tool_name: str = Field(..., min_length=1, max_length=200)
    arguments: dict[str, Any] = Field(
        ..., description="Arguments the agent is about to pass to the tool"
    )
    source_context: str | None = Field(
        default=None,
        max_length=MAX_SOURCE_CONTEXT_LENGTH,
        description=(
            "Optional raw text the arguments were derived from (e.g. the "
            "webpage or document the agent read before deciding to call "
            "this tool). Checking this in addition to the arguments catches "
            "injections that influenced the call but didn't end up copied "
            "verbatim into the arguments."
        ),
    )

    @field_validator("arguments")
    @classmethod
    def validate_arguments_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > MAX_ARGUMENT_FIELDS:
            raise ValueError(
                f"Too many argument fields ({len(value)}); max is {MAX_ARGUMENT_FIELDS}"
            )
        for key, val in value.items():
            text = str(val)
            if len(text) > MAX_FIELD_VALUE_LENGTH:
                raise ValueError(
                    f"Argument '{key}' is too long ({len(text)} chars); "
                    f"max is {MAX_FIELD_VALUE_LENGTH}"
                )
        return value


class TierResult(BaseModel):
    """Result from a single detection tier."""

    tier: str
    triggered: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class InspectResponse(BaseModel):
    decision: Literal["allow", "block"]
    resolved_tier: str = Field(
        ..., description="Which tier made the final decision (allow or block)"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    tier_results: list[TierResult] = Field(default_factory=list)
    latency_ms: float


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Human-readable label for this key")
