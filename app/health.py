"""
Health checks.

A health endpoint that always returns "ok" is worse than no health
endpoint at all -- it gives orchestration tooling (load balancers,
k8s liveness/readiness probes) false confidence that an instance is
usable when its actual dependencies (the audit DB, the judge model
backend) might be down.

This module actually exercises each dependency:
  - DB: runs a trivial query against the real configured DB file.
  - Judge backend: pings Ollama's /api/tags (lightweight, no model call)
    or confirms an OpenAI key is configured, depending on JUDGE_BACKEND.

The judge backend is reported as a separate "degraded" component rather
than failing the whole health check -- if the judge model is temporarily
unreachable, tiers 1-2 still work and most traffic never needs tier 3, so
the service is still meaningfully "up".
"""

from __future__ import annotations

import sqlite3

import httpx

from app.config import settings


def check_database() -> tuple[bool, str]:
    try:
        conn = sqlite3.connect(settings.db_path, timeout=2.0)
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"unreachable: {exc}"


async def check_judge_backend() -> tuple[bool, str]:
    if settings.judge_backend == "openai":
        if settings.openai_api_key:
            return True, "configured"
        return False, "OPENAI_API_KEY not set"

    # ollama: ping the lightweight /api/tags endpoint rather than issuing
    # an actual chat completion, so the health check itself stays cheap.
    tags_url = settings.ollama_url.replace("/api/chat", "/api/tags")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(tags_url)
            resp.raise_for_status()
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"unreachable: {exc}"


async def run_health_checks() -> dict:
    db_ok, db_detail = check_database()
    judge_ok, judge_detail = await check_judge_backend()

    # The service is "ok" as long as its core dependency (the audit DB)
    # is reachable. The judge backend being down is reported as
    # "degraded", not a hard failure -- tiers 1-2 still protect most
    # traffic without it.
    if not db_ok:
        status = "down"
    elif not judge_ok:
        status = "degraded"
    else:
        status = "ok"

    return {
        "status": status,
        "components": {
            "database": {"ok": db_ok, "detail": db_detail},
            "judge_backend": {
                "ok": judge_ok,
                "detail": judge_detail,
                "backend": settings.judge_backend,
            },
        },
    }
