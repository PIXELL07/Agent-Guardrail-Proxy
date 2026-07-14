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
from pydantic import BaseModel, Field


class ToolCallPayload(BaseModel):
    """What the agent is about to send to a tool."""

    agent_id: str = Field(..., description="Identifier of the calling agent/session")
    tool_name: str = Field(..., description="Name of the tool about to be invoked")
    arguments: dict[str, Any] = Field(
        ..., description="Arguments the agent is about to pass to the tool"
    )
    source_context: str | None = Field(
        default=None,
        description=(
            "Optional raw text the arguments were derived from (e.g. the "
            "webpage or document the agent read before deciding to call "
            "this tool). Checking this in addition to the arguments catches "
            "injections that influenced the call but didn't end up copied "
            "verbatim into the arguments."
        ),
    )


class TierResult(BaseModel):
    """Result from a single detection tier."""

    tier: str
    triggered: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class InspectResponse(BaseModel):
    decision: Literal["allow", "block"]
    triggered_tier: str | None = Field(
        default=None, description="Which tier made the final call, if blocked"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    tier_results: list[TierResult] = Field(default_factory=list)
    latency_ms: float
