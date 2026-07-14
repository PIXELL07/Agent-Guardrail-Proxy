"""
SQLite-backed audit log.

Every inspection (allowed or blocked) gets written here, along with which
tier made the call and why. This is what powers the "post-hoc security
review" story: if something slips through, or if you want to see how often
each tier is firing, this table is the source of truth.

We use raw sqlite3 rather than an ORM on purpose here -- the schema is
small and stable, and it keeps the dependency footprint (and thing you have
to explain in an interview) minimal.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "guardrail.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    agent_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('allow', 'block')),
    triggered_tier TEXT,
    confidence REAL NOT NULL,
    reason TEXT NOT NULL,
    tier_results_json TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    latency_ms REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_agent ON audit_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_audit_decision ON audit_log(decision);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
"""


def init_db(db_path: Path = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def write_audit_entry(
    *,
    agent_id: str,
    tool_name: str,
    decision: str,
    triggered_tier: str | None,
    confidence: float,
    reason: str,
    tier_results: list[dict],
    arguments: dict,
    latency_ms: float,
    db_path: Path = DB_PATH,
) -> int:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO audit_log (
                ts, agent_id, tool_name, decision, triggered_tier,
                confidence, reason, tier_results_json, arguments_json, latency_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                agent_id,
                tool_name,
                decision,
                triggered_tier,
                confidence,
                reason,
                json.dumps(tier_results),
                json.dumps(arguments),
                latency_ms,
            ),
        )
        conn.commit()
        return cur.lastrowid


def fetch_recent(limit: int = 100, db_path: Path = DB_PATH) -> list[dict]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def fetch_stats(db_path: Path = DB_PATH) -> dict:
    with get_conn(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM audit_log").fetchone()["c"]
        blocked = conn.execute(
            "SELECT COUNT(*) AS c FROM audit_log WHERE decision = 'block'"
        ).fetchone()["c"]
        by_tier = conn.execute(
            """
            SELECT triggered_tier, COUNT(*) AS c
            FROM audit_log
            WHERE decision = 'block'
            GROUP BY triggered_tier
            """
        ).fetchall()
        return {
            "total_inspections": total,
            "total_blocked": blocked,
            "block_rate": (blocked / total) if total else 0.0,
            "blocks_by_tier": {r["triggered_tier"]: r["c"] for r in by_tier},
        }
