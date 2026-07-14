from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db, write_audit_entry, fetch_recent, fetch_stats
from app.pipeline import DetectionPipeline
from app.schemas import ToolCallPayload, InspectResponse

pipeline: DetectionPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    init_db()
    # Fitting the similarity/classifier models happens once here, at
    # startup, not on every request -- this is what keeps per-request
    # latency low for tiers 1-2.
    pipeline = DetectionPipeline(judge_backend="ollama")
    yield


app = FastAPI(
    title="Agent Guardrail Proxy",
    description="Detects prompt injection attempts in LLM agent tool-call payloads",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/v1/inspect", response_model=InspectResponse)
async def inspect(payload: ToolCallPayload) -> InspectResponse:
    result = await pipeline.inspect(payload)

    write_audit_entry(
        agent_id=payload.agent_id,
        tool_name=payload.tool_name,
        decision=result.decision,
        triggered_tier=result.triggered_tier,
        confidence=result.confidence,
        reason=result.reason,
        tier_results=[tr.model_dump() for tr in result.tier_results],
        arguments=payload.arguments,
        latency_ms=result.latency_ms,
    )
    return result


@app.get("/v1/audit")
async def audit(limit: int = 100):
    return {"entries": fetch_recent(limit=limit)}


@app.get("/v1/stats")
async def stats():
    return fetch_stats()


@app.get("/health")
async def health():
    return {"status": "ok"}
