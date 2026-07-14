"""
Prometheus metrics.

Structured logs (app/logging_config.py) tell you what happened to one
request. Metrics tell you the shape of traffic over time -- request rate,
latency percentiles, block rate trend -- without scraping and parsing log
lines yourself. Both matter; they're not redundant.

Exposed at GET /metrics in Prometheus text format. That endpoint requires
API key auth like everything else here (see app/main.py) -- scraping it
means configuring a bearer_token in your Prometheus scrape config, not
leaving operational data (tool names, agent ids, block rates) on an
unauthenticated port.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest

inspections_total = Counter(
    "guardrail_inspections_total",
    "Total number of tool-call inspections",
    ["decision", "resolved_tier"],
)

inspection_latency_ms = Histogram(
    "guardrail_inspection_latency_ms",
    "Latency of the detection pipeline in milliseconds",
    buckets=(0.5, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000),
)

http_requests_total = Counter(
    "guardrail_http_requests_total",
    "Total HTTP requests handled",
    ["method", "path", "status_code"],
)


def record_inspection(decision: str, resolved_tier: str, latency_ms: float) -> None:
    inspections_total.labels(decision=decision, resolved_tier=resolved_tier).inc()
    inspection_latency_ms.observe(latency_ms)


def record_http_request(method: str, path: str, status_code: int) -> None:
    http_requests_total.labels(method=method, path=path, status_code=str(status_code)).inc()


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
