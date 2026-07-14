from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.auth import verify_api_key, verify_master_key
from app.api_keys import generate_key, list_keys, revoke_key
from app.config import settings
from app.db import init_db, write_audit_entry, fetch_recent, fetch_stats
from app.health import run_health_checks
from app.logging_config import configure_logging, logger
from app.metrics import record_inspection, record_http_request, render_metrics
from app.pipeline import DetectionPipeline
from app.rate_limit import enforce_rate_limit
from app.schemas import ToolCallPayload, InspectResponse, ApiKeyCreateRequest

pipeline: DetectionPipeline | None = None


def check_production_cors_safety() -> None:
    """
    Raises RuntimeError if the app is configured to start with wildcard
    CORS in production. Extracted as its own function so it's directly
    unit-testable without needing to trigger a real ASGI startup event.
    """
    if (
        settings.environment == "production"
        and settings.cors_origins.strip() == "*"
        and not settings.allow_wildcard_cors_in_production
    ):
        raise RuntimeError(
            "Refusing to start with CORS_ORIGINS=* while ENVIRONMENT=production. "
            "Set CORS_ORIGINS to a comma-separated allowlist of real origins, or "
            "set ALLOW_WILDCARD_CORS_IN_PRODUCTION=true if you've deliberately "
            "decided this API has no browser-based callers to protect against."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()

    # Fail fast rather than silently serving with an open CORS policy --
    # a wildcard origin combined with credentials (as here, since
    # Authorization headers are how every endpoint is protected) means
    # any website's JavaScript could call this API using a visitor's
    # browser as a relay. This is deliberately a hard startup failure,
    # not a warning log that's easy to miss.
    check_production_cors_safety()

    global pipeline
    init_db()
    # Fitting the similarity/classifier models happens once here, at
    # startup, not on every request -- this is what keeps per-request
    # latency low for tiers 1-2.
    pipeline = DetectionPipeline()
    logger.info(
        "guardrail_proxy_started",
        extra={"judge_backend": settings.judge_backend, "db_path": settings.db_path},
    )
    yield


app = FastAPI(
    title="Agent Guardrail Proxy",
    description="Detects prompt injection attempts in LLM agent tool-call payloads",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_size_limit_middleware(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            size = int(content_length)
        except ValueError:
            size = None
        if size is not None and size > settings.max_request_body_bytes:
            logger.info(
                "request_rejected_too_large",
                extra={"path": request.url.path, "content_length": size},
            )
            return JSONResponse(
                status_code=413,
                content={
                    "detail": (
                        f"Request body too large ({size} bytes); "
                        f"max is {settings.max_request_body_bytes} bytes"
                    )
                },
            )
    return await call_next(request)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "http_request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    record_http_request(request.method, request.url.path, response.status_code)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        extra={"path": request.url.path, "error": str(exc)},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.post("/v1/inspect", response_model=InspectResponse, dependencies=[Depends(verify_api_key)])
async def inspect(payload: ToolCallPayload) -> InspectResponse:
    enforce_rate_limit(payload.agent_id)

    result = await pipeline.inspect(payload)

    write_audit_entry(
        agent_id=payload.agent_id,
        tool_name=payload.tool_name,
        decision=result.decision,
        resolved_tier=result.resolved_tier,
        confidence=result.confidence,
        reason=result.reason,
        tier_results=[tr.model_dump() for tr in result.tier_results],
        arguments=payload.arguments,
        latency_ms=result.latency_ms,
    )

    record_inspection(result.decision, result.resolved_tier, result.latency_ms)

    logger.info(
        "inspection_completed",
        extra={
            "agent_id": payload.agent_id,
            "tool_name": payload.tool_name,
            "decision": result.decision,
            "resolved_tier": result.resolved_tier,
            "latency_ms": round(result.latency_ms, 2),
        },
    )
    return result


@app.get("/v1/audit", dependencies=[Depends(verify_api_key)])
async def audit(limit: int = 100):
    return {"entries": fetch_recent(limit=limit)}


@app.get("/v1/stats", dependencies=[Depends(verify_api_key)])
async def stats():
    return fetch_stats()


@app.post("/v1/admin/keys", dependencies=[Depends(verify_master_key)])
async def create_key(payload: ApiKeyCreateRequest):
    """
    Issues a new API key. The raw key is returned exactly once here --
    only its hash is stored, so if it's lost the only recovery is
    revoking it and issuing a new one.
    """
    result = generate_key(name=payload.name)
    logger.info("api_key_created", extra={"key_id": result["id"], "key_name": payload.name})
    return result


@app.get("/v1/admin/keys", dependencies=[Depends(verify_master_key)])
async def get_keys():
    """Lists issued keys -- metadata only, never the hash or raw value."""
    return {"keys": list_keys()}


@app.delete("/v1/admin/keys/{key_id}", dependencies=[Depends(verify_master_key)])
async def delete_key(key_id: int):
    revoked = revoke_key(key_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Key not found or already revoked")
    logger.info("api_key_revoked", extra={"key_id": key_id})
    return {"revoked": True, "key_id": key_id}


@app.get("/metrics", dependencies=[Depends(verify_api_key)])
async def metrics():
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


@app.get("/health")
async def health():
    result = await run_health_checks()
    status_code = 503 if result["status"] == "down" else 200
    return JSONResponse(status_code=status_code, content=result)
